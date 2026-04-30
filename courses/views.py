from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required ,user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Count, Avg
from django.utils import timezone
from .models import Course, Lesson, Enrollment, Profile, Category, Assignment, Submission, Announcement, Department, LessonDownload, Notification, CourseResult, CourseFeedback, Report
from .forms import CourseForm, LessonForm, StudentRegistrationForm, AssignmentForm, SubmissionForm, AnnouncementForm, InstructorRegistrationForm, ProfileUpdateForm, CourseFeedbackForm, ReportForm
from django.views.decorators.cache import never_cache
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

def register_student(request):
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = StudentRegistrationForm()
    return render(request, 'auth/register_student.html', {'form': form, 'page_title': 'Student Registration'})

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages


def _handle_login(request, role):
    error = None

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:

            # 🔒 Safety check
            if not hasattr(user, 'profile'):
                error = "Profile not found."
                return error, None

            profile = user.profile

            # 🚫 GLOBAL SUSPENSION CHECK
            if profile.is_suspended:
                error = "🚫 Your account has been suspended."
                return error, None

            # 🎯 ROLE HANDLING
            if role == "student":
                if profile.is_instructor:
                    error = "⚠️ You are not a student. Use the instructor tab."
                    return error, None

            elif role == "instructor":
                if not profile.is_instructor:
                    error = "⚠️ You are not an instructor. Use the student tab."
                    return error, None

                if not profile.is_approved:
                    error = "⏳ Your instructor account is awaiting moderator approval."
                    return error, None

            elif role == "moderator":
                if not profile.is_moderator:
                    error = "⚠️ You are not authorized as a moderator."
                    return error, None

            # ✅ LOGIN SUCCESS
            login(request, user)
            return None, redirect('dashboard')

        else:
            error = "Invalid username or password."

    return error, None


def login_student(request):
    error, response = _handle_login(request, "student")
    if response:
        return response

    return render(request, 'auth/login.html', {
        'student_error': error,
        'show_tab': 'student'
    })


def register_instructor(request):
    if request.method == 'POST':
        form = InstructorRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            user.profile.is_instructor = True
            user.profile.is_approved = False
            user.profile.save()
            return render(request, 'auth/pending_approval.html', {
                'page_title': 'Pending Approval'
            })
        else:
            print("❌ Form errors:", form.errors)
    else:
        form = InstructorRegistrationForm()     

    return render(request, 'auth/register_instructor.html', {
        'form': form,
        'page_title': 'Instructor Registration'
    })




def login_instructor(request):
    error, response = _handle_login(request, "instructor")
    if response:
        return response

    return render(request, 'auth/login.html', {
        'instructor_error': error,
        'show_tab': 'instructor'
    })

def login_moderator(request):
    error, response = _handle_login(request, "moderator")
    if response:
        return response

    return render(request, 'auth/login.html', {
        'moderator_error': error,
        'show_tab': 'moderator'
    })


@login_required
def logout_view(request):
    logout(request)
    return redirect('login_student')

def home(request):
    latest_courses = Course.objects.all()[:5]
    return render(request, 'index.html', {'latest_courses': latest_courses})



from django.db.models import Count, Avg, Q

def course_list(request):
    sort_by = request.GET.get('sort', 'popular')
    category_id = request.GET.get('category')
    search_query = request.GET.get('search')
    difficulty = request.GET.get('difficulty')
    min_duration = request.GET.get('min_duration')
    max_duration = request.GET.get('max_duration')

    if request.user.is_authenticated and request.user.profile.is_instructor:
        courses = Course.objects.filter(created_by=request.user)
    else:
        courses = Course.objects.all()

    # ✅ ADD RATING + COUNT
    courses = courses.annotate(
        num_students=Count('enrollment'),
        avg_rating=Avg('feedbacks__rating'),
        feedback_count=Count('feedbacks')
    )

    if category_id:
        courses = courses.filter(category_id=category_id)

    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) |
            Q(created_by__username__icontains=search_query)
        )

    if difficulty:
        courses = courses.filter(difficulty=difficulty)

    if min_duration:
        courses = courses.filter(duration_days__gte=min_duration)

    if max_duration:
        courses = courses.filter(duration_days__lte=max_duration)

    if sort_by == 'popular':
        courses = courses.order_by('-num_students')
    elif sort_by == 'newest':
        courses = courses.order_by('-created_at')
    elif sort_by == 'oldest':
        courses = courses.order_by('created_at')
    elif sort_by == 'rating':
        courses = courses.order_by('-avg_rating', '-feedback_count')

    paginator = Paginator(courses, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "courses/course_grid.html", {
            "page_obj": page_obj
        })

    return render(request, 'courses/course_list.html', {
        'page_obj': page_obj,
        'categories': categories,
    })




@login_required
def course_detail(request, course_id):

    # 🔥 Redirect moderator
    if request.user.profile.is_moderator:
        return redirect('moderator_course_detail', course_id=course_id)

    course = get_object_or_404(Course, id=course_id)
    lessons = course.lessons.all()

    enrollment = None
    enrolled = False
    submissions = {}
    assignment_due_dates = {}

    # ✅ Instructor override
    is_instructor = request.user == course.created_by

    if is_instructor:
        enrolled = True
    else:
        # ✅ Get enrollment (only approved)
        enrollment = Enrollment.objects.filter(
            student=request.user,
            course=course,
            is_approved=True
        ).first()

        enrolled = enrollment is not None

    # ✅ Assignments logic
    assignments = course.assignments.all()

    for assignment in assignments:

        submission = None

        # Only students have submissions
        if enrollment:
            submission = Submission.objects.filter(
                assignment=assignment,
                enrollment=enrollment
            ).first()

            assignment_due_dates[assignment.id] = (
                enrollment.get_assignment_due_date(assignment)
            )

        submissions[assignment.id] = submission

    # ✅ Feedback
    feedbacks = course.feedbacks.select_related('student').order_by('-created_at')
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg']

    return render(request, 'courses/course_detail.html', {
        'course': course,
        'lessons': lessons,
        'enrolled': enrolled,
        'is_instructor': is_instructor,  # ⭐ NEW
        'submissions': submissions,
        'assignment_due_dates': assignment_due_dates,
        'enrollment': enrollment,
        'feedbacks': feedbacks,
        'avg_rating': avg_rating,
    })


def choose_registration(request):
    return render(request, 'auth/choose_registration.html', {
        'page_title': 'Register'
    })

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Course, Enrollment


@login_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    user = request.user

    # 🚫 Block instructors & moderators
    if user.profile.is_instructor or user.profile.is_moderator:
        messages.error(request, "You are not allowed to enroll in courses.")
        return redirect('course_detail', course_id=course.id)

    # 🚫 Prevent instructor enrolling in own course (extra safety)
    if user == course.created_by:
        messages.error(request, "You cannot enroll in your own course.")
        return redirect('course_detail', course_id=course.id)

    # ✅ Get or create enrollment
    enrollment, created = Enrollment.objects.get_or_create(
        student=user,
        course=course,
        defaults={
            'is_approved': False,
            'enrolled_at': timezone.now()
        }
    )

    # 🔁 If already exists
    if not created:
        if enrollment.is_approved:
            messages.info(request, "You are already enrolled in this course.")
            return redirect('course_detail', course_id=course.id)
        else:
            messages.info(request, "Your enrollment request is pending approval.")
            return render(request, 'students/pending_enrollment.html', {'course': course})

    # 🔔 Notify instructor (only on new request)
    Notification.objects.create(
        user=course.created_by,
        message=f"{user.username} requested enrollment for {course.title}",
        link="/instructor/enrollments/"
    )

    # ✅ New request
    messages.success(request, "Your enrollment request has been sent for approval.")
    return render(request, 'students/pending_enrollment.html', {'course': course})

from django.db.models import Q

@login_required
def manage_enrollments(request):
    instructor_courses = Course.objects.filter(created_by=request.user)

    course_id = request.GET.get('course')
    search_query = request.GET.get('search')
    sort_by = request.GET.get('sort', 'newest')

    pending_enrollments = Enrollment.objects.filter(
        course__created_by=request.user,
        is_approved=False
    )

    approved_enrollments = Enrollment.objects.filter(
        course__created_by=request.user,
        is_approved=True
    )

    if course_id:
        pending_enrollments = pending_enrollments.filter(course_id=course_id)
        approved_enrollments = approved_enrollments.filter(course_id=course_id)

    if search_query:
        pending_enrollments = pending_enrollments.filter(
            Q(student__username__icontains=search_query) |
            Q(student__email__icontains=search_query)
        )

        approved_enrollments = approved_enrollments.filter(
            Q(student__username__icontains=search_query) |
            Q(student__email__icontains=search_query)
        )

    if sort_by == 'name':
        approved_enrollments = approved_enrollments.order_by('student__username')
        pending_enrollments = pending_enrollments.order_by('student__username')
    elif sort_by == 'email':
        approved_enrollments = approved_enrollments.order_by('student__email')
        pending_enrollments = pending_enrollments.order_by('student__email')
    elif sort_by == 'course':
        approved_enrollments = approved_enrollments.order_by('course__title')
        pending_enrollments = pending_enrollments.order_by('course__title')
    elif sort_by == 'oldest':
        approved_enrollments = approved_enrollments.order_by('enrolled_at')
        pending_enrollments = pending_enrollments.order_by('enrolled_at')
    else:
        approved_enrollments = approved_enrollments.order_by('-enrolled_at')
        pending_enrollments = pending_enrollments.order_by('-enrolled_at')

    pending_count = pending_enrollments.count()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "instructors/enrollment_table.html", {
            "pending_enrollments": pending_enrollments,
            "approved_enrollments": approved_enrollments,
        })

    return render(request, 'instructors/manage_enrollments.html', {
        'pending_enrollments': pending_enrollments,
        'approved_enrollments': approved_enrollments,
        'instructor_courses': instructor_courses,
        'selected_course': course_id,
        'pending_count': pending_count,
    })




@login_required
def approve_enrollment(request, enrollment_id):

    enrollment = get_object_or_404(
        Enrollment,
        id=enrollment_id,
        course__created_by=request.user
    )

    if not enrollment.is_approved:
        enrollment.is_approved = True
        enrollment.save()

        # 🔔 Notification (with type)
        Notification.objects.create(
            user=enrollment.student,
            message=f"You are approved for {enrollment.course.title}",
            link=f"/courses/{enrollment.course.id}/",
            type="enrollment"
        )

        messages.success(
            request,
            f"{enrollment.student.username} has been approved for {enrollment.course.title}."
        )

    else:
        messages.info(request, "Student is already approved.")

    return redirect('manage_enrollments')


@login_required
def remove_enrollment(request, enrollment_id):

    enrollment = get_object_or_404(
        Enrollment,
        id=enrollment_id,
        course__created_by=request.user
    )

    student_name = enrollment.student.username
    course_title = enrollment.course.title

    enrollment.delete()

    # 🔔 Optional notification (recommended)
    Notification.objects.create(
        user=enrollment.student,
        message=f"You have been removed from {course_title}",
        link="/courses/",
        type="enrollment"
    )

    messages.success(
        request,
        f"{student_name} has been removed from {course_title}."
    )

    return redirect('manage_enrollments')


from django.db.models import Q
from django.db.models import Count
from django.utils import timezone
@never_cache
@login_required

def dashboard(request):
    user = request.user

    unread_notifications_count = user.notifications.filter(is_read=False).count() if user.is_authenticated else 0
    latest_announcement = Announcement.objects.order_by('-created_at').first()

    # =========================
    # 🛡️ MODERATOR
    # =========================
    if hasattr(user, "profile") and user.profile.is_moderator:

        total_students = Profile.objects.filter(
            is_instructor=False,
            is_moderator=False
        ).count()

        total_instructors = Profile.objects.filter(
            is_instructor=True
        ).count()
        approved_count = Profile.objects.filter(
            is_instructor=True,
            is_approved=True
        ).count()

        pending_count = Profile.objects.filter(
            is_instructor=True,
            is_approved=False
        ).count()

        total_courses = Course.objects.count()

        # 🔥 Pending instructors (only 3 for display)
        all_pending_instructors = Profile.objects.filter(
            is_instructor=True,
            is_approved=False
        ).select_related("user", "department").order_by("-user__date_joined")

        pending_instructors = all_pending_instructors[:3]
        pending_instructors_count = all_pending_instructors.count()

        year_qs = (
            Profile.objects
            .filter(
                is_instructor=False,
                is_moderator=False,
                year__isnull=False
            )
            .values("year")
            .annotate(count=Count("id"))
            .order_by("year")
        )

        year_labels = []
        year_values = []

        for item in year_qs:
            year_labels.append(f"Year {item['year']}")
            year_values.append(item["count"])

        dept_qs = (
            Profile.objects
            .filter(
                is_instructor=False,
                is_moderator=False,
                department__isnull=False
            )
            .values("department__name")
            .annotate(student_count=Count("id"))
            .order_by("-student_count")
        )

        dept_labels = [d["department__name"] for d in dept_qs]
        dept_values = [d["student_count"] for d in dept_qs]

        return render(request, 'auth/dashboard.html', {
            'is_moderator': True,
            'total_students': total_students,
            'total_instructors': total_instructors,
            'total_courses': total_courses,

            # approvals
            'pending_instructors': pending_instructors,
            'pending_instructors_count': pending_instructors_count,

            # chart
            'dept_labels': dept_labels,
            'dept_values': dept_values,
            "year_labels": year_labels,
            "year_values": year_values,

            # existing
            'latest_announcement': latest_announcement,
            'unread_notifications_count': unread_notifications_count,


        })

    # =========================
    # ⏳ PENDING APPROVAL
    # =========================
    if user.profile.is_instructor and not user.profile.is_approved:
        return render(request, 'auth/pending_approval.html')

    # =========================
    # 👨‍🏫 INSTRUCTOR
    # =========================
    if user.profile.is_instructor:

        courses = Course.objects.filter(created_by=user)

        total_assignments = Assignment.objects.filter(
            course__in=courses
        ).count()

        enrollments = Enrollment.objects.filter(
            course__in=courses,
            is_approved=True
        ).select_related('student')

        students = list({enrollment.student for enrollment in enrollments})

        # 🔥 Pending Work
        pending_enrollments_count = Enrollment.objects.filter(
            course__in=courses,
            is_approved=False
        ).count()

        pending_submissions_count = Submission.objects.filter(
            assignment__course__in=courses,
            status="submitted"
        ).count()

        pending_results_count = sum(
            1 for e in enrollments
            if e.progress_percentage == 100 and not hasattr(e, "course_result")
        )

        return render(request, 'auth/dashboard.html', {
            'is_instructor': True,
            'courses': courses,
            'students': students,
            'latest_announcement': latest_announcement,
            'unread_notifications_count': unread_notifications_count,
            'total_assignments': total_assignments,

            'pending_enrollments_count': pending_enrollments_count,
            'pending_submissions_count': pending_submissions_count,
            'pending_results_count': pending_results_count,
        })

    # =========================
    # 🎓 STUDENT DASHBOARD
    # =========================
    enrollments = user.enrollments.select_related('course').filter(is_approved=True)
    completed_courses_count = sum(
        1 for e in enrollments
        if e.completed_lessons.count() == e.course.lessons.count()
    )
    # Progress
    for enrollment in enrollments:
        enrollment.progress = enrollment.progress_percentage

    enrolled_course_ids = enrollments.values_list('course', flat=True)

    # Pending assignments
    pending_assignments = Assignment.objects.filter(
        course__in=enrolled_course_ids
    ).exclude(
        submissions__enrollment__student=user
    ).distinct().select_related('course')

    # Add days left
    for assignment in pending_assignments:
        enrollment = enrollments.filter(course=assignment.course).first()

        if enrollment:
            due_date = enrollment.get_assignment_due_date(assignment)

            if due_date:
                assignment.days_left = max((due_date - timezone.now()).days, 0)
            else:
                assignment.days_left = 0
        else:
            assignment.days_left = 0

    pending_count = pending_assignments.count()

    # Remaining classes
    remaining_classes = sum(
        enrollment.course.lessons.count() -
        enrollment.completed_lessons.count()
        for enrollment in enrollments
    )

    # =========================
    # 🌍 POPULAR COURSES
    # =========================
    popular_courses = Course.objects.annotate(
    total_students=Count("enrollment")
    ).order_by("-total_students")[:5]

    # =========================
    # 👨‍🏫 TOP INSTRUCTORS
    # =========================
    top_instructors = User.objects.filter(
        profile__is_instructor=True,
        profile__is_approved=True
    ).annotate(
        total_students=Count("course__enrollment")
    ).order_by("-total_students")[:5]

    # =========================
    # 🎯 FINAL RENDER
    # =========================
    return render(request, 'auth/dashboard.html', {
    'is_instructor': False,
    'enrollments': enrollments,
    'pending_assignments': pending_assignments,
    'pending_count': pending_count,
    'remaining_classes': remaining_classes,
    'latest_announcement': latest_announcement,
    'popular_courses': popular_courses,
    'top_instructors': top_instructors,
    'unread_notifications_count': unread_notifications_count,
    'completed_courses_count': completed_courses_count,
})




@login_required
def create_course(request):
    if not request.user.profile.is_instructor:
        return HttpResponseForbidden("You are not an instructor.")
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.created_by = request.user
            course.save()
            return redirect('course_list')
    else:
        form = CourseForm()
    return render(request, 'courses/create_course.html', {'form': form, 'page_title': 'Create Course'})


@login_required
def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.user != course.created_by:
        return HttpResponseForbidden("Not allowed.")
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            return redirect('course_detail', course_id=course.id)
    else:
        form = CourseForm(instance=course)
    return render(request, 'courses/create_course.html', {'form': form, 'page_title': 'Edit Course'})


@login_required
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.user != course.created_by:
        return HttpResponseForbidden("Not allowed.")
    course.delete()
    return redirect('course_list')


@login_required
def create_lesson(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if course.created_by != request.user:
        return HttpResponseForbidden("Not allowed.")

    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)  # 🔥 important
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            return redirect('course_detail', course_id=course.id)
    else:
        form = LessonForm()

    return render(request, 'courses/create_lesson.html', {
        'form': form,
        'course': course,
        'page_title': 'Add Lesson'
    })


def courses_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    courses = Course.objects.filter(category=category)
    categories = Category.objects.all()

    paginator = Paginator(courses, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'courses/course_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category,
        'show_sidebar': True,
        'full_page_center': False,
    })


def login_page(request):
    return render(request, 'auth/login.html')


@login_required
def create_assignment(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if not request.user.profile.is_instructor or course.created_by != request.user:
        return HttpResponseForbidden("Only the instructor of this course can create assignments.")

    if request.method == 'POST':
        form = AssignmentForm(request.POST, course=course)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.course = course
            assignment.created_by = request.user
            assignment.save()
            return redirect('course_detail', course_id=course.id)
    else:
        form = AssignmentForm(course=course)

    return render(request, 'assignments/create_assignment.html', {
        'form': form,
        'course': course,
        'page_title': 'Create Assignment'
    })


@login_required
def assignment_list(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    assignments = course.assignments.all()
    return render(request, 'assignments/assignment_list.html', {
        'course': course,
        'assignments': assignments,
    })


@login_required
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    Notification.objects.create(
        user=assignment.created_by,
        message=f"{request.user.username} submitted {assignment.title}",
        link=f"/assignments/{assignment.id}/submissions/"
    )    
    enrollment = Enrollment.objects.filter(
        student=request.user,
        course=assignment.course,
        is_approved=True
    ).first()

    if not enrollment:
        messages.error(request, "You must enroll in this course to submit assignments.")
        return redirect('course_detail', course_id=assignment.course.id)

    submissions = Submission.objects.filter(
        assignment=assignment,
        enrollment=enrollment
    ).order_by("-submitted_at")

    attempt_count = submissions.count()
    latest_submission = submissions.first()

    if latest_submission and latest_submission.status == "approved":
        messages.warning(request, "This assignment is already approved.")
        return redirect("student_assignments")

    if latest_submission and latest_submission.status == "submitted":
        messages.info(request, "Your submission is currently under review.")
        return redirect("student_assignments")

    if attempt_count >= 5:
        messages.error(request, "Maximum attempts reached. You cannot resubmit this assignment.")
        return redirect("student_assignments")

    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)

        if form.is_valid():
            submission = form.save(commit=False)
            submission.assignment = assignment
            submission.enrollment = enrollment
            submission.status = "submitted"
            submission.save()

            messages.success(request, f"Assignment submitted successfully! Attempt {attempt_count + 1}/5")
            return redirect("student_assignments")

    else:
        form = SubmissionForm()

    return render(request, "assignments/submit_assignment.html", {
        "form": form,
        "assignment": assignment,
        "attempts_left": 5 - attempt_count
    })

@login_required
def view_submissions(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if not request.user.profile.is_instructor or assignment.created_by != request.user:
        return HttpResponseForbidden("Only the instructor can view submissions.")
    
    submissions = assignment.submissions.select_related(
    "enrollment__student"
)

    return render(request, 'assignments/view_submissions.html', {
        'assignment': assignment,
        'submissions': submissions
    })

@login_required
def student_assignments(request):
    if request.user.profile.is_instructor:
        return HttpResponseForbidden("Instructors cannot access student assignments.")

    enrollments = Enrollment.objects.filter(
        student=request.user,
        is_approved=True
    ).select_related('course')

    enrollment_map = {e.course.id: e for e in enrollments}

    assignments = Assignment.objects.filter(
        course__in=enrollment_map.keys()
    ).select_related('course')

    submissions = Submission.objects.filter(
        enrollment__student=request.user
    ).select_related('assignment')

    submission_map = {s.assignment.id: s for s in submissions}

    pending_list = []
    reviewed_list = []
    rejected_list = []

    for assignment in assignments:
        enrollment = enrollment_map.get(assignment.course.id)

        due_date = None
        if enrollment:
            due_date = enrollment.get_assignment_due_date(assignment)

        submission = submission_map.get(assignment.id)

        attempt_count = Submission.objects.filter(
            assignment=assignment,
            enrollment=enrollment
        ).count()

        latest_submission = Submission.objects.filter(
            assignment=assignment,
            enrollment=enrollment
        ).order_by("-submitted_at").first()

        assignment_info = {
            'assignment': assignment,
            'due_date': due_date,
            'submission': latest_submission,
            'attempt_count': attempt_count,
            'attempts_left': 5 - attempt_count
        }

        if submission:
            if submission.status == "rejected":
                rejected_list.append(assignment_info)
            else:
                reviewed_list.append(assignment_info)
        else:
            pending_list.append(assignment_info)

    return render(request, 'assignments/student_assignments.html', {
        'pending_assignments': pending_list,
        'submitted_assignments': reviewed_list,
        'rejected_assignments': rejected_list,
    })

@login_required
def pending_classes(request):
    if request.user.profile.is_instructor:
        return HttpResponseForbidden("Instructors cannot access pending classes.")

    enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    pending_lessons = []

    for enrollment in enrollments:
        completed = enrollment.completed_lessons.values_list('id', flat=True)
        lessons_left = enrollment.course.lessons.exclude(id__in=completed)
        for lesson in lessons_left:
            pending_lessons.append({
                'course': enrollment.course,
                'lesson': lesson,
            })

    return render(request, 'courses/pending_classes.html', {
        'pending_lessons': pending_lessons,
        'page_title': 'Pending Classes',
    })

@login_required
def announcement_list(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    announcements = course.announcements.all()
    return render(request, 'announcements/announcement_list.html', {
        'course': course,
        'announcements': announcements,
    })

@login_required
def create_announcement(request):

    if not request.user.profile.is_instructor:
        return redirect('global_announcement_list')

    courses = Course.objects.filter(created_by=request.user)

    if request.method == "POST":

        form = AnnouncementForm(request.POST)

        if form.is_valid():

            announcement = form.save(commit=False)

            course_id = request.POST.get("course_id")

            if course_id:
                course = get_object_or_404(
                    Course,
                    id=course_id,
                    created_by=request.user
                )
                announcement.course = course

            announcement.created_by = request.user
            announcement.save()

            # 🔔 Notify all enrolled students
            enrollments = Enrollment.objects.filter(
                course=announcement.course,
                is_approved=True
            ).exclude(student=request.user)

            for enrollment in enrollments:
                Notification.objects.create(
                    user=enrollment.student,
                    message=f"New announcement in {announcement.course.title}: {announcement.title}",
                    link=f"/courses/{announcement.course.id}/announcements/"
                )

            return redirect("global_announcement_list")

    else:
        form = AnnouncementForm()

    return render(request, "announcements/announcement_form.html", {
        "form": form,
        "courses": courses
    })

from django.db.models import Q

@login_required
def global_announcement_list(request):

    sort = request.GET.get("sort", "latest")

    if request.user.profile.is_moderator:

        announcements = Announcement.objects.all().select_related(
            "course", "created_by"
        )

        courses = None

    elif request.user.profile.is_instructor:

        announcements = Announcement.objects.filter(
            course__created_by=request.user
        ).select_related("course", "created_by")

        courses = Course.objects.filter(created_by=request.user)

    else:

        enrolled_courses = Enrollment.objects.filter(
            student=request.user,
            is_approved=True
        ).values_list('course', flat=True)

        announcements = Announcement.objects.filter(
            course__in=enrolled_courses
        ).select_related("course", "created_by")

        courses = None

    # ✅ APPLY SORTING HERE
    if sort == "oldest":
        announcements = announcements.order_by("created_at")
    else:
        announcements = announcements.order_by("-created_at")

    return render(request, 'announcements/announcement_list.html', {
        'announcements': announcements,
        'courses': courses
    })


def is_moderator(user):
    return hasattr(user, 'profile') and user.profile.is_moderator

@login_required
@user_passes_test(is_moderator)
def pending_instructors(request):
    pending_instructors = Profile.objects.filter(is_instructor=True, is_approved=False)
    pending_count = pending_instructors.count()
    return render(request, 'instructors/pending_instructors.html', {
        'pending_instructors': pending_instructors,
        'pending_count': pending_count,
    })



@login_required
@user_passes_test(is_moderator)
def approve_instructor(request, user_id):
    instructor = get_object_or_404(User, id=user_id, profile__is_instructor=True)

    instructor.profile.is_approved = True
    instructor.profile.save()

    send_mail(
        subject="🎉 Your Instructor Account Has Been Approved",
        message=f"""
Hello {instructor.username},

Good news! Your instructor registration has been approved.

You can now log in and start creating courses.

Regards,
LAP Administration
""",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[instructor.email],
        fail_silently=True,
    )

    return redirect('instructors')



@login_required
def all_instructors(request):
    if not request.user.profile.is_moderator:
        return render(request, 'error.html', {'message': 'Unauthorized access.'})

    instructors = User.objects.filter(
        profile__is_instructor=True
    ).select_related('profile').order_by('username')

    pending_instructors = Profile.objects.filter(
        is_instructor=True,
        is_approved=False
    ).select_related('user')

    return render(request, 'moderator/all_instructors.html', {
        'instructors': instructors,
        'pending_instructors': pending_instructors,
    })

@login_required
@user_passes_test(is_moderator)
def remove_instructor(request, user_id):
    instructor = get_object_or_404(User, id=user_id, profile__is_instructor=True)

    send_mail(
        subject="⚠ Instructor Registration Rejected",
        message=f"""
Hello {instructor.username},

We regret to inform you that your instructor registration was not approved.

If you believe this was an error, please contact administration.

Regards,
LAP Administration
""",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[instructor.email],
        fail_silently=True,
    )

    instructor.profile.is_approved = False
    instructor.profile.save()

    return redirect('instructors')

from django.db.models import Q

@login_required
@user_passes_test(is_moderator)
def instructors(request):

    search_query = request.GET.get("search")
    sort_by = request.GET.get("sort", "newest")
    status_filter = request.GET.get("status")
    department_filter = request.GET.get("department")

    instructors = Profile.objects.filter(is_instructor=True).select_related("user", "department")

    if search_query:
        instructors = instructors.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    if status_filter == "approved":
        instructors = instructors.filter(is_approved=True)
    elif status_filter == "pending":
        instructors = instructors.filter(is_approved=False)

    if department_filter:
        instructors = instructors.filter(department_id=department_filter)

    if sort_by == "name":
        instructors = instructors.order_by("user__username")
    elif sort_by == "email":
        instructors = instructors.order_by("user__email")
    elif sort_by == "department":
        instructors = instructors.order_by("department__name")
    elif sort_by == "status":
        instructors = instructors.order_by("is_approved")
    elif sort_by == "oldest":
        instructors = instructors.order_by("user__date_joined")
    else:
        instructors = instructors.order_by("-user__date_joined")

    departments = Department.objects.all()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "moderator/instructor_table.html", {
            "instructors": instructors
        })

    return render(request, "moderator/instructors.html", {
        "instructors": instructors,
        "departments": departments,
        "total_instructors_count": Profile.objects.filter(is_instructor=True).count(),
        "approved_count": Profile.objects.filter(is_instructor=True, is_approved=True).count(),
        "pending_count": Profile.objects.filter(is_instructor=True, is_approved=False).count(),
    })



from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.contrib.auth.models import User
from datetime import timedelta
from collections import OrderedDict

@login_required
def moderator_stats(request):

    if not request.user.profile.is_moderator:
        return HttpResponseForbidden("Unauthorized")

    # =========================
    # DATE FILTER
    # =========================
    try:
        days = int(request.GET.get("days", 30))
    except (TypeError, ValueError):
        days = 30

    if days not in [7, 30, 90]:
        days = 30

    start_date = timezone.now() - timedelta(days=days)

    # =========================
    # TOTAL COUNTS
    # =========================
    total_instructors = Profile.objects.filter(is_instructor=True).count()

    approved_instructors = Profile.objects.filter(
        is_instructor=True,
        is_approved=True
    ).count()

    pending_instructors = Profile.objects.filter(
        is_instructor=True,
        is_approved=False
    ).count()

    total_students = Profile.objects.filter(
        is_instructor=False,
        is_moderator=False
    ).count()

    total_courses = Course.objects.count()

    # =========================
    # REPORTS OVERVIEW
    # =========================
    total_reports = Report.objects.count()
    pending_reports = Report.objects.filter(status="pending").count()
    resolved_reports = Report.objects.filter(status="resolved").count()
    recent_reports = Report.objects.filter(created_at__gte=start_date).count()

    student_reporters = Report.objects.filter(
        reported_by__profile__is_instructor=False,
        reported_by__profile__is_moderator=False
    )
    instructor_reporters = Report.objects.filter(
        reported_by__profile__is_instructor=True
    )

    student_reports = student_reporters.count()
    instructor_reports = instructor_reporters.count()
    recent_student_reports = student_reporters.filter(created_at__gte=start_date).count()
    recent_instructor_reports = instructor_reporters.filter(created_at__gte=start_date).count()

    report_resolution_rate = 0
    if total_reports > 0:
        report_resolution_rate = round((resolved_reports / total_reports) * 100, 1)

    # =========================
    # RECENT GROWTH
    # =========================
    recent_students = User.objects.filter(
        profile__is_instructor=False,
        profile__is_moderator=False,
        date_joined__gte=start_date
    ).count()

    recent_courses = Course.objects.filter(
        created_at__gte=start_date
    ).count()

    # =========================
    # APPROVAL RATE
    # =========================
    approval_rate = 0
    if total_instructors > 0:
        approval_rate = round(
            (approved_instructors / total_instructors) * 100,
            1
        )

    # =========================
    # DEPARTMENT CONTRIBUTION
    # =========================
    dept_qs = (
        Profile.objects
        .filter(
            is_instructor=False,
            is_moderator=False,
            department__isnull=False
        )
        .values("department__name")
        .annotate(student_count=Count("id"))
        .order_by("-student_count")
    )

    dept_labels = []
    dept_values = []

    for dept in dept_qs:
        dept_labels.append(dept["department__name"])
        dept_values.append(dept["student_count"])

    # =========================
    # TOP COURSE CATEGORIES
    # =========================
    top_categories_qs = (
        Course.objects
        .filter(category__isnull=False)
        .values("category__name")
        .annotate(total_enrollments=Count("enrollment"))
        .order_by("-total_enrollments")[:3]
    )

    top_categories = []

    for cat in top_categories_qs:
        percentage = 0
        if total_students > 0:
            percentage = round(
                (cat["total_enrollments"] / total_students) * 100,
                1
            )

        top_categories.append({
            "name": cat["category__name"],
            "enrollments": cat["total_enrollments"],
            "percentage": percentage
        })

    # =========================
    # TOP 5 COURSES
    # =========================
    top_courses_qs = (
        Course.objects
        .annotate(total_enrollments=Count("enrollment"))
        .order_by("-total_enrollments")[:4]
    )

    top_courses = []

    for course in top_courses_qs:
        percentage = 0
        if total_students > 0:
            percentage = round(
                (course.total_enrollments / total_students) * 100,
                1
            )

        top_courses.append({
            "course": course,
            "enrollments": course.total_enrollments,
            "percentage": percentage
        })

    # =========================
    # CONTEXT
    # =========================
    context = {
        "days": days,

        # Totals
        "total_instructors": total_instructors,
        "approved_instructors": approved_instructors,
        "pending_instructors": pending_instructors,
        "total_students": total_students,
        "total_courses": total_courses,

        # Growth
        "recent_students": recent_students,
        "recent_courses": recent_courses,
        "recent_reports": recent_reports,

        # Approval
        "approval_rate": approval_rate,

        # Reports
        "total_reports": total_reports,
        "pending_reports": pending_reports,
        "resolved_reports": resolved_reports,
        "student_reports": student_reports,
        "instructor_reports": instructor_reports,
        "recent_student_reports": recent_student_reports,
        "recent_instructor_reports": recent_instructor_reports,
        "report_resolution_rate": report_resolution_rate,

        # Department Pie
        "dept_labels": dept_labels,
        "dept_values": dept_values,

        # Category Ranking
        "top_categories": top_categories,

        # Course Ranking
        "top_courses": top_courses,
    }

    return render(request, "moderator/moderator_stats.html", context)

@login_required
def student_detail(request, enrollment_id):

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    # ✅ safer permission check
    if not Enrollment.objects.filter(
        id=enrollment_id,
        course__created_by=request.user
    ).exists():
        return HttpResponseForbidden("You are not allowed to view this student.")

    student = enrollment.student

    student_enrollments = Enrollment.objects.filter(
        student=student,
        is_approved=True,
        course__created_by=request.user
    ).select_related("course")

    return render(request, "instructors/student_detail.html", {
        "student": student,
        "student_enrollments": student_enrollments,
    })

@login_required
def student_course_detail(request, enrollment_id):
    enrollment = get_object_or_404(
        Enrollment,
        id=enrollment_id,
        is_approved=True,
        course__created_by=request.user
    )

    lessons = enrollment.course.lessons.all()

    context = {
        "enrollment": enrollment,
        "lessons": lessons,
    }

    return render(request, "instructors/student_course_detail.html", context)

@login_required
def approve_submission(request, submission_id):
    submission = get_object_or_404(
        Submission,
        id=submission_id,
        assignment__created_by=request.user
    )
    Notification.objects.create(
        user=submission.enrollment.student,
        message=f"Your assignment '{submission.assignment.title}' was graded ({submission.marks}/10)",
        link="/assignments/"
    )

    due_date = submission.enrollment.get_assignment_due_date(submission.assignment)
    is_late = due_date and submission.submitted_at > due_date

    if request.method == "POST":
        marks = int(request.POST.get("marks"))

        if 0 <= marks <= 10:
            submission.status = "approved"
            submission.marks = marks
            submission.feedback = None
            submission.save()

            messages.success(request, "Submission approved successfully.")
            return redirect('view_submissions', assignment_id=submission.assignment.id)

    return render(request, "assignments/approve_submission.html", {
        "submission": submission,
        "is_late": is_late,
        "due_date": due_date
    })
    
@login_required
def reject_submission(request, submission_id):
    submission = get_object_or_404(
        Submission,
        id=submission_id,
        assignment__created_by=request.user
    )
    Notification.objects.create(
        user=submission.enrollment.student,
        message=f"Your assignment '{submission.assignment.title}' was rejected",
        link="/assignments/"
    )
    if request.method == "POST":
        reason = request.POST.get("reason")

        submission.status = "rejected"
        submission.marks = None
        submission.feedback = reason
        submission.save()

        messages.warning(request, "Submission rejected.")
        return redirect('view_submissions', assignment_id=submission.assignment.id)

    return render(request, "assignments/reject_submission.html", {
        "submission": submission
    })

@login_required
def instructor_latest_submissions(request):

    if not request.user.profile.is_instructor:
        return HttpResponseForbidden("Only instructors allowed.")

    # ================= BASE QUERY =================
    submissions = Submission.objects.filter(
        assignment__created_by=request.user
    ).select_related(
        "assignment",
        "assignment__course",
        "enrollment__student",
        "enrollment__student__profile"
    )

    # ================= FILTER PARAMS =================
    search = request.GET.get('search')
    course = request.GET.get('course')
    status = request.GET.get('status')
    sort = request.GET.get('sort')

    # ================= FILTERING =================
    if search:
        submissions = submissions.filter(
            Q(enrollment__student__username__icontains=search) |
            Q(enrollment__student__email__icontains=search)
        )

    if course:
        submissions = submissions.filter(
            assignment__course_id=course
        )

    if status:
        submissions = submissions.filter(status=status)

    # ================= ORDER BASE =================
    submissions = submissions.order_by("-submitted_at")

    # ================= LATEST + ATTEMPT LOGIC =================
    latest_map = {}
    attempt_map = {}

    for sub in submissions:
        key = (sub.assignment.id, sub.enrollment.student.id)

        attempt_map[key] = attempt_map.get(key, 0) + 1

        if key not in latest_map:
            latest_map[key] = sub

    latest_submissions = []

    for key, sub in latest_map.items():

        sub.attempt_count = attempt_map[key]

        due_date = sub.enrollment.get_assignment_due_date(sub.assignment)

        sub.is_late = (
            due_date is not None and
            sub.submitted_at > due_date
        )

        sub.due_date = due_date

        latest_submissions.append(sub)

    # ================= SORTING =================
    if sort == "oldest":
        latest_submissions.sort(key=lambda x: x.submitted_at)
    else:
        latest_submissions.sort(key=lambda x: x.submitted_at, reverse=True)

    # ================= EXTRA DATA (FOR FILTERS UI) =================
    instructor_courses = Course.objects.filter(created_by=request.user)

    return render(request, "instructors/latest_submissions.html", {
        "submissions": latest_submissions,
        "instructor_courses": instructor_courses,
    })

@login_required
def instructor_detail(request, user_id):
    if not request.user.profile.is_moderator:
        return HttpResponseForbidden("Unauthorized")

    instructor = get_object_or_404(
        User.objects.select_related("profile"),
        id=user_id,
        profile__is_instructor=True
    )

    courses = Course.objects.filter(created_by=instructor)

    return render(request, "moderator/instructor_detail.html", {
        "instructor": instructor,
        "profile": instructor.profile,
        "courses": courses
    })

from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

@login_required
def moderator_students(request):

    if not request.user.profile.is_moderator:
        return HttpResponseForbidden("Unauthorized")

    students = Profile.objects.filter(
        is_instructor=False,
        is_moderator=False
    ).select_related("user", "department").annotate(
        enrollment_count=Count("user__enrollments")
    )

    # 🔎 Search
    search = request.GET.get("search")
    if search:
        students = students.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )

    # 🏢 Department Filter
    department = request.GET.get("department")
    if department:
        students = students.filter(department__id=department)

    # 📊 Enrollment Filter
    enrollment_filter = request.GET.get("enrollment")
    if enrollment_filter == "active":
        students = students.filter(enrollment_count__gt=0)
    elif enrollment_filter == "none":
        students = students.filter(enrollment_count=0)

    # ↕ Sorting
    sort = request.GET.get("sort", "date_joined")

    if sort == "name":
        students = students.order_by("user__username")
    elif sort == "enrollments":
        students = students.order_by("-enrollment_count")
    else:
        students = students.order_by("-user__date_joined")

    departments = Department.objects.all()

    context = {
        "students": students,
        "departments": departments,
        "search": search,
        "selected_department": department,
        "sort": sort,
        "enrollment_filter": enrollment_filter,
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "moderator/student_table.html", {
            "students": students,
        })
    return render(request, "moderator/moderator_students.html", context)

import csv
from django.http import HttpResponse

@login_required
def export_students_csv(request):

    if not request.user.profile.is_moderator:
        return HttpResponseForbidden("Unauthorized")

    students = Profile.objects.filter(
        is_instructor=False,
        is_moderator=False
    ).select_related("user", "department").annotate(
        enrollment_count=Count("user__enrollments")
    )

    # Apply same filters as page
    search = request.GET.get("search", "").strip()
    if search:
        students = students.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )

    department = request.GET.get("department", "").strip()
    if department and department.isdigit():
        students = students.filter(department__id=int(department))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students.csv"'

    writer = csv.writer(response)

    writer.writerow([
        "Username",
        "Email",
        "Department",
        "Enrollments",
        "Date Joined"
    ])

    for profile in students:
        writer.writerow([
            profile.user.username,
            profile.user.email,
            profile.department.name if profile.department else "-",
            profile.enrollment_count,
            profile.user.date_joined.strftime("%Y-%m-%d")
        ])

    return response

@login_required
def export_instructors_csv(request):

    if not request.user.profile.is_moderator:
        return HttpResponseForbidden("Unauthorized")

    instructors = Profile.objects.filter(
        is_instructor=True
    ).select_related("user", "department")

    search = request.GET.get("search", "").strip()
    if search:
        instructors = instructors.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )

    department = request.GET.get("department", "").strip()
    if department and department.isdigit():
        instructors = instructors.filter(department__id=int(department))

    status = request.GET.get("status", "").strip()
    if status == "approved":
        instructors = instructors.filter(is_approved=True)
    elif status == "pending":
        instructors = instructors.filter(is_approved=False)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="instructors.csv"'

    writer = csv.writer(response)

    writer.writerow([
        "Username",
        "Email",
        "Department",
        "Status",
        "Date Joined"
    ])

    for profile in instructors:
        writer.writerow([
            profile.user.username,
            profile.user.email,
            profile.department.name if profile.department else "-",
            "Approved" if profile.is_approved else "Pending",
            profile.user.date_joined.strftime("%Y-%m-%d")
        ])

    return response

from django.http import JsonResponse

def session_check(request):
    if request.user.is_authenticated:
        return JsonResponse({"authenticated": True})
    return JsonResponse({"authenticated": False}, status=401)

@login_required
def profile_view(request):
    return render(request, "auth/profile.html", {
        "profile": request.user.profile
    })

@login_required
def edit_profile(request):
    profile = request.user.profile

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("profile")
    else:
        form = ProfileUpdateForm(instance=profile)

    return render(request, "auth/edit_profile.html", {
        "form": form
    })

@login_required
def my_enrolled_courses(request):
    if request.user.profile.is_instructor:
        return HttpResponseForbidden("Only students allowed.")

    enrollments = Enrollment.objects.filter(
        student=request.user,
        is_approved=True
    ).select_related(
        "course",
        "course__created_by",
        "course_result"
    ).prefetch_related(
        "course__assignments",
        "submissions"
    )

    for enrollment in enrollments:

        assignments = enrollment.course.assignments.all()
        total = assignments.count()

        completed = 0

        for assignment in assignments:
            submissions = enrollment.submissions.filter(
                assignment=assignment
            )

            latest = submissions.order_by("-submitted_at").first()

            if not latest:
                continue

            if latest.status == "approved" or submissions.count() >= 5:
                completed += 1

        enrollment.total_assignments = total
        enrollment.completed_assignments = completed
        enrollment.pending_assignments = max(0, total - completed)
        enrollment.expiry_date = enrollment.course_end_date

        if hasattr(enrollment, "course_result") and enrollment.course_result.graded:
            enrollment.status = "verified"
        elif enrollment.progress_percentage == 100:
            enrollment.status = "completed"
        else:
            enrollment.status = "pending"

    return render(request, "students/my_courses.html", {
        "enrollments": enrollments
    })

from django.http import FileResponse
import os

@login_required
def download_lesson_material(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    enrollment = Enrollment.objects.filter(
        student=request.user,
        course=lesson.course,
        is_approved=True
    ).first()

    if not enrollment:
        messages.error(request, "Enroll in the course to access materials.")
        return redirect('course_detail', course_id=lesson.course.id)   

    if not lesson.material:
        return HttpResponseForbidden("No file available.")

    download_obj, created = LessonDownload.objects.get_or_create(
        student=request.user,
        lesson=lesson
    )

    download_obj.download_count += 1
    download_obj.save()

    return FileResponse(lesson.material.open(), as_attachment=True)

@login_required
def student_downloads(request):
    downloads = LessonDownload.objects.filter(
        student=request.user
    ).select_related(
        "lesson",
        "lesson__course",
        "lesson__course__category"
    )

    search = request.GET.get("search")
    category = request.GET.get("category")
    course = request.GET.get("course")
    sort = request.GET.get("sort", "latest")

    if search:
        downloads = downloads.filter(
            lesson__title__icontains=search
        )

    if category:
        downloads = downloads.filter(
            lesson__course__category_id=category
        )

    if course:
        downloads = downloads.filter(
            lesson__course_id=course
        )

    if sort == "oldest":
        downloads = downloads.order_by("downloaded_at")
    else:
        downloads = downloads.order_by("-downloaded_at")

    categories = Category.objects.all()
    enrolled_courses = Course.objects.filter(
        enrollment__student=request.user,
        enrollment__is_approved=True
    )

    return render(request, "students/downloads.html", {
        "downloads": downloads,
        "categories": categories,
        "enrolled_courses": enrolled_courses,
    })

from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Count, Q

@login_required
@user_passes_test(is_moderator)
def moderator_courses(request):

    courses = Course.objects.annotate(
        total_students=Count("enrollment")
    ).select_related("created_by", "category").distinct()

    search = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "most_students")

    if search:
        courses = courses.filter(
            Q(title__icontains=search) |
            Q(created_by__username__icontains=search)
        )
    total_courses = Course.objects.count()

    total_enrollments = Enrollment.objects.count()

    avg_students = 0
    if total_courses > 0:
        avg_students = round(total_enrollments / total_courses, 1)

    if sort == "least_students":
        courses = courses.order_by("total_students", "-created_at")
    elif sort == "newest":
        courses = courses.order_by("-created_at")
    elif sort == "oldest":
        courses = courses.order_by("created_at")
    else:
        courses = courses.order_by("-total_students", "-created_at")

    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        html = render_to_string(
            "moderator/course_list.html",
            {"courses": courses},
            request=request
        )
        return JsonResponse({"html": html})

    return render(request, "moderator/moderator_courses.html", {
        "courses": courses,
        "search": search,
        "sort": sort,

        "total_courses": total_courses,
        "total_enrollments": total_enrollments,
        "avg_students": avg_students,
    })

@login_required
def submission_history(request, assignment_id, student_id):

    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        created_by=request.user
    )

    enrollment = get_object_or_404(
        Enrollment,
        student_id=student_id,
        course=assignment.course
    )

    submissions = Submission.objects.filter(
        assignment=assignment,
        enrollment=enrollment
    ).order_by("submitted_at")

    return render(request, "assignments/submission_history.html", {
        "assignment": assignment,
        "student": enrollment.student,
        "submissions": submissions
    })

@login_required
def notifications(request):

    notifications = request.user.notifications.order_by("-created_at")

    unread_notifications = notifications.filter(is_read=False)

    if unread_notifications.exists():
        unread_notifications.update(is_read=True)

    context = {
        "notifications": notifications
    }

    return render(request, "auth/notifications.html", context)

from django.db.models import Sum
@login_required
def finalize_course_result(request, enrollment_id):

    enrollment = get_object_or_404(
        Enrollment,
        id=enrollment_id,
        course__created_by=request.user
    )

    assignments = Assignment.objects.filter(course=enrollment.course)

    submissions = Submission.objects.filter(
        enrollment=enrollment
    ).select_related("assignment").order_by("-submitted_at")

    total_assignments = assignments.count()

    approved_submissions = submissions.filter(status="approved")

    completed_assignments = approved_submissions.values("assignment").distinct().count()

    total_score = approved_submissions.aggregate(
        total=Sum("marks")
    )["total"] or 0

    max_score = total_assignments * 10

    score_percent = 0
    if max_score > 0:
        score_percent = round((total_score / max_score) * 100, 2)

    completion_rate = 0
    if total_assignments > 0:
        completion_rate = round((completed_assignments / total_assignments) * 100, 2)

    if request.method == "POST":
        marks = request.POST.get("marks")

        if marks is not None:
            CourseResult.objects.update_or_create(
                enrollment=enrollment,
                defaults={
                    "total_marks": int(marks),
                    "graded": True,
                    "graded_at": timezone.now(),
                }
            )

            enrollment.completed = True
            enrollment.save()

            Notification.objects.create(
                user=enrollment.student,
                message=f"Your final result for {enrollment.course.title} has been published.",
                link="/courses/my-courses/"
            )

        return redirect("student_detail", enrollment_id=enrollment.id)

    return render(request, "courses/finalize_course_result.html", {
        "enrollment": enrollment,
        "submissions": submissions,
        "total_score": total_score,
        "score_percent": score_percent,
        "completion_rate": completion_rate,
        "total_assignments": total_assignments,
        "completed_assignments": completed_assignments,
    })

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import date

@login_required
def download_certificate(request, enrollment_id):

    enrollment = get_object_or_404(
        Enrollment,
        id=enrollment_id,
        student=request.user,
        course_result__graded=True
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="certificate_{enrollment.course.title}.pdf"'

    p = canvas.Canvas(response, pagesize=letter)

    width, height = letter

    p.setFont("Helvetica-Bold", 28)
    p.drawCentredString(width/2, height-150, "Certificate of Completion")

    p.setFont("Helvetica", 16)
    p.drawCentredString(width/2, height-220, "This is to certify that")

    p.setFont("Helvetica-Bold", 22)
    p.drawCentredString(width/2, height-260, enrollment.student.get_full_name() or enrollment.student.username)

    p.setFont("Helvetica", 16)
    p.drawCentredString(width/2, height-310, "has successfully completed the course")

    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width/2, height-350, enrollment.course.title)

    p.setFont("Helvetica", 14)
    p.drawCentredString(width/2, height-400, f"Final Score: {enrollment.course_result.total_marks}/100")

    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, height-450, f"Issued on {date.today()}")

    p.showPage()
    p.save()

    return response

from django.db.models import Count

@login_required
def instructor_leaderboard(request):

    instructors = User.objects.filter(
        profile__is_instructor=True,
        profile__is_approved=True
    )

    leaderboard = []

    for instructor in instructors:

        courses = Course.objects.filter(created_by=instructor)

        enrollments = Enrollment.objects.filter(
            course__in=courses,
            is_approved=True
        )

        submissions = Submission.objects.filter(
            assignment__course__in=courses
        )

        students = enrollments.count()
        course_count = courses.count()

        completion_rates = [e.progress_percentage for e in enrollments]
        completion_rate = sum(completion_rates) / len(completion_rates) if completion_rates else 0

        total = submissions.count()
        approved = submissions.filter(status="approved").count()

        assignment_success = (approved / total) * 100 if total > 0 else 0

        score = (
            students * 0.4 +
            course_count * 5 +
            completion_rate * 0.2 +
            assignment_success * 0.15
        )

        # 🔥 ADD THIS (TOP COURSES)
        top_courses = courses.annotate(
            total_students=Count("enrollment")
        ).order_by("-total_students")[:3]

        leaderboard.append({
            "instructor": instructor,
            "students": students,
            "courses": course_count,
            "completion_rate": round(completion_rate, 2),
            "assignment_success": round(assignment_success, 2),
            "score": round(score, 2),
            "top_courses": list(top_courses)   # IMPORTANT
        })

    leaderboard.sort(key=lambda x: x["score"], reverse=True)

    for i, entry in enumerate(leaderboard, start=1):
        entry["rank"] = i

    return render(request, "leaderboard/instructor_leaderboard.html", {
        "leaderboard": leaderboard
    })


@login_required
def instructor_courses(request, instructor_id):

    instructor = get_object_or_404(
        User,
        id=instructor_id,
        profile__is_instructor=True
    )

    courses = Course.objects.filter(
        created_by=instructor
    ).order_by("-created_at")

    return render(request, "courses/instructor_courses.html", {
        "instructor": instructor,
        "courses": courses
    })

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
import json

@login_required
def instructor_analytics(request):

    if not request.user.profile.is_instructor:
        return HttpResponseForbidden("Only instructors allowed.")

    courses = Course.objects.filter(created_by=request.user)

    # FILTER
    days = int(request.GET.get("days", 30))
    if days not in [7, 30, 90]:
        days = 30

    start_date = timezone.now() - timedelta(days=days)

    # KPIs
    total_courses = courses.count()

    enrollments = Enrollment.objects.filter(
        course__in=courses,
        is_approved=True
    )

    active_enrollments = enrollments.filter(
        enrolled_at__gte=start_date
    ).count()

    submissions = Submission.objects.filter(
        assignment__course__in=courses,
        submitted_at__gte=start_date
    )

    pending_submissions = submissions.filter(status="submitted").count()

    # ENGAGEMENT
    engagement_list = []

    for course in courses:
        total = Enrollment.objects.filter(course=course, is_approved=True).count()

        active = Submission.objects.filter(
            assignment__course=course,
            submitted_at__gte=start_date
        ).values("enrollment__student").distinct().count()

        engagement = round((active / total) * 100, 1) if total > 0 else 0

        engagement_list.append({
            "course": course.title,
            "engagement": engagement
        })

    engagement_list.sort(key=lambda x: x["engagement"], reverse=True)

    top_course = engagement_list[0] if engagement_list else None
    low_course = engagement_list[-1] if engagement_list else None

    avg_engagement = round(
        sum(e["engagement"] for e in engagement_list) / len(engagement_list),
        1
    ) if engagement_list else 0

    # INACTIVE STUDENTS
    active_students_ids = Submission.objects.filter(
        assignment__course__in=courses,
        submitted_at__gte=start_date
    ).values_list("enrollment__student", flat=True).distinct()

    inactive_students = enrollments.exclude(
        student__in=active_students_ids
    ).count()

    # DEPARTMENT DATA
    dept_data = enrollments.values(
        "student__profile__department__name"
    ).annotate(count=Count("id"))

    dept_labels = [
        d["student__profile__department__name"] or "Unknown"
        for d in dept_data
    ]
    dept_counts = [d["count"] for d in dept_data]

    # YEAR DATA
    year_data = enrollments.values(
        "student__profile__year"
    ).annotate(count=Count("id"))

    year_labels = [
        f"Year {y['student__profile__year']}" if y["student__profile__year"] else "Unknown"
        for y in year_data
    ]
    year_counts = [y["count"] for y in year_data]

    context = {
        "days": days,

        "total_courses": total_courses,
        "active_enrollments": active_enrollments,
        "pending_submissions": pending_submissions,
        "avg_engagement": avg_engagement,

        "top_course": top_course,
        "low_course": low_course,
        "inactive_students": inactive_students,

        "dept_labels": json.dumps(dept_labels),
        "dept_counts": json.dumps(dept_counts),

        "year_labels": json.dumps(year_labels),
        "year_counts": json.dumps(year_counts),
    }

    return render(request, "instructors/analytics.html", context)

@login_required
def redirect_to_publish(request):
    return redirect('pending_results_list')


@login_required
def pending_results_list(request):

    status = request.GET.get("status", "pending")

    courses = Course.objects.filter(created_by=request.user)

    enrollments = Enrollment.objects.filter(
        course__in=courses,
        is_approved=True
    ).select_related("student", "course")

    pending_results = []
    published_results = []

    for e in enrollments:
        if e.progress_percentage == 100:
            if hasattr(e, "course_result"):
                published_results.append(e)
            else:
                pending_results.append(e)

    if status == "published":
        results = published_results
    else:
        results = pending_results

    return render(request, "instructors/pending_results.html", {
        "results": results,
        "selected_status": status
    })

from django.shortcuts import get_object_or_404, render
from django.db.models import Count
from django.contrib.auth.decorators import login_required

@login_required
def instructor_detail(request, id):

    instructor = get_object_or_404(User, id=id, profile__is_instructor=True)

    courses = Course.objects.filter(created_by=instructor)

    enrollments = Enrollment.objects.filter(
        course__in=courses,
        is_approved=True
    )

    students = enrollments.count()
    course_count = courses.count()

    completion_rates = [e.progress_percentage for e in enrollments]
    completion_rate = sum(completion_rates) / len(completion_rates) if completion_rates else 0

    courses = courses.annotate(
        total_students=Count("enrollment")
    ).order_by("-total_students")

    context = {
        "instructor": instructor,
        "courses": courses,
        "students": students,
        "course_count": course_count,
        "completion_rate": round(completion_rate, 2)
    }

    return render(request, "leaderboard/instructor_detail.html", context)

from django.db.models import Count

from django.db.models import Count

@login_required
def instructors_list(request):

    sort = request.GET.get("sort", "default")
    department_id = request.GET.get("department")

    instructors = User.objects.filter(
        profile__is_instructor=True,
        profile__is_approved=True
    )

    # 🔥 FILTER BY DEPARTMENT
    if department_id:
        instructors = instructors.filter(profile__department_id=department_id)

    data = []

    for instructor in instructors:

        courses = Course.objects.filter(created_by=instructor)

        students = Enrollment.objects.filter(
            course__in=courses,
            is_approved=True
        ).count()

        data.append({
            "instructor": instructor,
            "course_count": courses.count(),
            "students": students
        })

    # 🔽 SORT
    if sort == "students":
        data.sort(key=lambda x: x["students"], reverse=True)
    elif sort == "courses":
        data.sort(key=lambda x: x["course_count"], reverse=True)
    else:
        data.sort(key=lambda x: x["instructor"].username)

    # 🔥 SEND DEPARTMENTS
    departments = Department.objects.all()

    return render(request, "leaderboard/instructors_list.html", {
        "instructors": data,
        "selected_sort": sort,
        "departments": departments,
        "selected_department": department_id
    })

@login_required
def submit_feedback(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    enrollment = Enrollment.objects.filter(
        student=request.user,
        course=course,
        is_approved=True
    ).first()

    if not enrollment:
        return HttpResponseForbidden("You must be enrolled.")

    if enrollment.progress_percentage < 100:
        return HttpResponseForbidden("You can only give feedback after completing the course.")

    existing = CourseFeedback.objects.filter(
        course=course,
        student=request.user
    ).first()

    if request.method == "POST":
        form = CourseFeedbackForm(request.POST, instance=existing)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.course = course
            feedback.student = request.user
            feedback.save()
            messages.success(request, "Feedback submitted!")
            return redirect('course_detail', course_id=course.id)
    else:
        form = CourseFeedbackForm(instance=existing)

    return render(request, "courses/submit_feedback.html", {
        "form": form,
        "course": course
    })

@login_required
def report_general(request):
    if request.method == "POST":
        form = ReportForm(request.POST, request.FILES)

        if form.is_valid():
            report = form.save(commit=False)
            report.reported_by = request.user

            # ✅ BASIC ANTI-SPAM
            existing = Report.objects.filter(
                reported_by=request.user,
                report_type=report.report_type,
                course=report.course,
                reported_user=report.reported_user,
                status='pending'
            ).first()

            if existing:
                messages.warning(request, "You already submitted a similar report.")
                return redirect('dashboard')

            report.save()
            # 🔔 Notify all moderators
            moderators = User.objects.filter(profile__is_moderator=True)

            for mod in moderators:
                Notification.objects.create(
                    user=mod,
                    message=f"🚨 Report: {report.report_type} - {report.reason} by {request.user.username}",
                    link="/moderator/reports/"
                )
            messages.success(request, "Report submitted successfully.")
            return redirect('dashboard')

    else:
        form = ReportForm()

    return render(request, "reports/report_form.html", {
        "form": form
    })

@login_required
@user_passes_test(is_moderator)
def moderator_reports(request):
    status = request.GET.get("status")

    reports = Report.objects.select_related(
        "reported_by",
        "course",
        "reported_user"
    ).order_by("-created_at")

    if status == "pending":
        reports = reports.filter(status="pending")
    elif status == "resolved":
        reports = reports.filter(status="resolved")
    else:
        status = "all"  # 👈 important default

    return render(request, "moderator/reports.html", {
        "reports": reports,
        "status": status,
    })

@login_required
@user_passes_test(is_moderator)
def resolve_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)

    report.status = "resolved"
    report.save()

    messages.success(request, "Report marked as resolved.")
    return redirect('moderator_reports')

@login_required
def moderator_course_detail(request, course_id):
    if not request.user.profile.is_moderator:
        return HttpResponseForbidden()

    course = get_object_or_404(Course, id=course_id)

    lessons = course.lessons.all()
    assignments = course.assignments.all()
    announcements = course.announcements.all()

    feedbacks = course.feedbacks.select_related('student').order_by('-created_at')
    avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg']

    return render(request, 'moderator/course_detail.html', {
        'course': course,
        'lessons': lessons,
        'assignments': assignments,
        'announcements': announcements,
        'feedbacks': feedbacks,
        'avg_rating': avg_rating,
    })

@login_required
@user_passes_test(is_moderator)
def warn_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    user.profile.warnings_count += 1
    user.profile.save()

    Notification.objects.create(
        user=user,
        message="⚠️ You have received a warning from moderator.",
        link="/profile/"
    )

    messages.success(request, "User warned successfully.")
    return redirect("moderator_reports")

@login_required
@user_passes_test(is_moderator)
def suspend_user(request, user_id):
    user = get_object_or_404(User, id=user_id)

    user.profile.is_suspended = True
    user.profile.save()

    Notification.objects.create(
        user=user,
        message="🚫 Your account has been suspended.",
        link="/"
    )

    messages.warning(request, "User suspended.")
    return redirect("moderator_reports")

@login_required
@user_passes_test(is_moderator)
def delete_reported_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    Notification.objects.create(
        user=course.created_by,
        message=f"⚠️ Your course '{course.title}' was removed by moderator.",
        link="/dashboard/"
    )

    course.delete()

    messages.success(request, "Course deleted.")
    return redirect("moderator_reports")
