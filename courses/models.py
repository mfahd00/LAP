from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.templatetags.static import static
from django.core.validators import MinValueValidator, MaxValueValidator


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_instructor = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    profile_pic = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    warnings_count = models.IntegerField(default=0)
    is_suspended = models.BooleanField(default=False)
    verification_document = models.FileField(
    upload_to='instructor_docs/',
    blank=True,
    null=True
    )
    YEAR_CHOICES = [
        (1, "Year 1"),
        (2, "Year 2"),
        (3, "Year 3"),
        (4, "Year 4"),
        (5, "Year 5"),
    ]

    year = models.PositiveSmallIntegerField(
        choices=YEAR_CHOICES,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.user.username

    @property
    def profile_image_url(self):
        if self.profile_pic and hasattr(self.profile_pic, 'url'):
            return self.profile_pic.url
        return static('images/default_profile.jpg')


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

class Category(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class Course(models.Model):
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('hard', 'Hard'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    duration_days = models.PositiveIntegerField(
        default=30,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(180)
        ],
        help_text="Course duration (1–180 days)"
    )

    def __str__(self):
        return self.title

    @property
    def student_count(self):
        return self.enrollment_set.count()


class Lesson(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    video_url = models.URLField(blank=True, null=True)
    course = models.ForeignKey(Course, related_name='lessons', on_delete=models.CASCADE)
    material = models.FileField(upload_to='lessons/materials/', blank=True, null=True)

    def __str__(self):
        return self.title

class Enrollment(models.Model):

    student = models.ForeignKey(
        User,
        related_name="enrollments",
        on_delete=models.CASCADE
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE
    )

    completed_lessons = models.ManyToManyField(
        Lesson,
        blank=True
    )

    enrolled_at = models.DateTimeField(
        default=timezone.now
    )

    is_approved = models.BooleanField(
        default=False
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course_enrollment"
            )
        ]

    def __str__(self):
        return f"{self.student.username} - {self.course.title}"

    @property
    def course_end_date(self):
        return self.enrolled_at + timedelta(days=self.course.duration_days)

    def get_assignment_due_date(self, assignment):
        return self.enrolled_at + timedelta(days=assignment.relative_due_days)

    @property
    def progress_percentage(self):

        assignments = self.course.assignments.all()
        total_assignments = assignments.count()

        if total_assignments == 0:
            return 0

        completed = 0

        for assignment in assignments:

            submissions = Submission.objects.filter(
                assignment=assignment,
                enrollment=self
            ).order_by("-submitted_at")

            latest = submissions.first()

            if not latest:
                continue

            if latest.status == "approved":
                completed += 1

            elif submissions.count() >= 5:
                completed += 1

        return int((completed / total_assignments) * 100)

    @property
    def is_expired(self):
        return timezone.now() > self.course_end_date

    @property
    def average_mark(self):

        approved = self.submissions.filter(
            status="approved",
            marks__isnull=False
        )

        if not approved.exists():
            return 0

        total = sum(sub.marks for sub in approved)

        return round(total / approved.count(), 2)


class Assignment(models.Model):
    course = models.ForeignKey(Course, related_name='assignments', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    relative_due_days = models.PositiveIntegerField(default=7, help_text="Days after enrollment this assignment is due")

    def __str__(self):
        return f"{self.title} ({self.course.title})"
    
    def get_due_date_for_student(self, student):
        from django.utils import timezone
        enrollment = self.course.enrollment_set.filter(student=student).first()
        if enrollment:
            return enrollment.enrolled_at + timezone.timedelta(days=self.relative_due_days)
        return None

class Submission(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    assignment = models.ForeignKey(
        Assignment,
        related_name='submissions',
        on_delete=models.CASCADE
    )

    attempt = models.IntegerField(default=1)
    enrollment = models.ForeignKey(
    Enrollment,
    related_name='submissions',
    on_delete=models.CASCADE,
)


    submitted_file = models.FileField(upload_to='assignments/submissions/')
    submitted_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="submitted"
    )

    marks = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Marks out of 10"
    )

    feedback = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.enrollment.student.username} - {self.assignment.title}"


class Announcement(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class LessonDownload(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now=True)
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('student', 'lesson')

    def __str__(self):
        return f"{self.student.username} - {self.lesson.title}"

class CourseResult(models.Model):

    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="course_result"
    )

    total_marks = models.PositiveIntegerField(null=True, blank=True)
    graded = models.BooleanField(default=False)

    graded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.enrollment.student.username} - {self.enrollment.course.title}"

class Notification(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    message = models.CharField(max_length=255)

    link = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    type = models.CharField(max_length=50, blank=True, null=True)
    def __str__(self):
        return f"{self.user.username} - {self.message}"

class CourseFeedback(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="feedbacks")
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(
        choices=[(i, f"{i} ⭐") for i in range(1, 6)]
    )
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('course', 'student')

    def __str__(self):
        return f"{self.student.username} - {self.course.title} ({self.rating})"

class Report(models.Model):

    REPORT_TYPE_CHOICES = [
        ('course', 'Course'),
        ('user', 'User'),
        ('other', 'Other'),
    ]

    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate Content'),
        ('abuse', 'Abusive Behavior'),
        ('other', 'Other'),
    ]

    reported_by = models.ForeignKey(User, on_delete=models.CASCADE)

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    reported_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports_against"
    )

    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('resolved', 'Resolved')],
        default='pending'
    )
    attachment = models.FileField(
        upload_to='report_attachments/',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.report_type} - {self.reason}"