from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from courses import views as course_views
from . import views


urlpatterns = [

    # ================= HOME =================
    path('', course_views.home, name='home'),

    # ================= COURSES =================
    path('courses/', course_views.course_list, name='course_list'),
    path('courses/<int:course_id>/', course_views.course_detail, name='course_detail'),
    path('courses/create/', course_views.create_course, name='create_course'),
    path('courses/<int:course_id>/edit/', course_views.edit_course, name='edit_course'),
    path('courses/<int:course_id>/delete/', course_views.delete_course, name='delete_course'),
    path('courses/<int:course_id>/add_lesson/', course_views.create_lesson, name='create_lesson'),
    path('courses/<int:course_id>/enroll/', course_views.enroll_course, name='enroll_course'),

    # ================= AUTH =================
    path('register/', views.choose_registration, name='register'),
    path('register/student/', views.register_student, name='register_student'),
    path('register/instructor/', views.register_instructor, name='register_instructor'),

    path('login/', views.login_page, name='login'),
    path('login/moderator/', views.login_moderator, name='login_moderator'),
    path('login/student/', views.login_student, name='login_student'),
    path('login/instructor/', views.login_instructor, name='login_instructor'),
    path('logout/', views.logout_view, name='logout'),

    # Password Reset
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='auth/password_reset.html'
        ),
        name='password_reset'
    ),
    path(
        'password_reset_done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='auth/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='auth/password_reset_confirm.html'
        ),
        name='password_reset_confirm'
    ),
    path(
        'reset_done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='auth/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    # ================= MODERATOR =================
    path('moderator/instructors/', views.instructors, name='instructors'),
    path('moderator/approve/<int:user_id>/', views.approve_instructor, name='approve_instructor'),
    path('moderator/remove/<int:user_id>/', views.remove_instructor, name='remove_instructor'),
    path('moderator/stats/', views.moderator_stats, name='moderator_stats'),
    path('moderator/instructor/<int:user_id>/', views.instructor_detail, name='instructor_detail'),
    path('moderator/students/', views.moderator_students, name='moderator_students'),
    path('moderator/students/export/', views.export_students_csv, name='export_students_csv'),
    path('moderator/instructors/export/', views.export_instructors_csv, name='export_instructors_csv'),
    path('moderator/courses/', views.moderator_courses, name='moderator_courses'),
    path('moderator/course/<int:course_id>/', views.moderator_course_detail, name='moderator_course_detail'),
    path('moderator/reports/', views.moderator_reports, name='moderator_reports'),
    path('moderator/reports/<int:report_id>/resolve/', views.resolve_report, name='resolve_report'),
    path("moderator/warn/<int:user_id>/", views.warn_user, name="warn_user"),
    path("moderator/suspend/<int:user_id>/", views.suspend_user, name="suspend_user"),
    path("moderator/delete-course/<int:course_id>/", views.delete_reported_course, name="delete_reported_course"),

    # ================= INSTRUCTOR =================
    path('instructor/enrollments/', views.manage_enrollments, name='manage_enrollments'),
    path('instructor/enrollments/approve/<int:enrollment_id>/', views.approve_enrollment, name='approve_enrollment'),
    path('instructor/enrollments/remove/<int:enrollment_id>/', views.remove_enrollment, name='remove_enrollment'),
    path('instructor/submissions/', views.instructor_latest_submissions, name='instructor_latest_submissions'),
    path('instructor/<int:id>/', views.instructor_detail, name='instructor_detail'),
    path('instructor/<int:instructor_id>/courses/', views.instructor_courses, name='instructor_courses'),
    path('instructor/analytics/', views.instructor_analytics, name='instructor_analytics'),
    path('instructor/pending-results/', views.pending_results_list, name='pending_results_list'),

    # ================= STUDENT =================
    path('student/<int:enrollment_id>/', views.student_detail, name='student_detail'),
    path('student/<int:enrollment_id>/course/', views.student_course_detail, name='student_course_detail'),
    path('my-courses/', views.my_enrolled_courses, name='my_enrolled_courses'),

    # ================= ASSIGNMENTS =================
    path('courses/<int:course_id>/assignments/', views.assignment_list, name='assignment_list'),
    path('courses/<int:course_id>/assignments/create/', views.create_assignment, name='create_assignment'),
    path('assignments/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
    path('assignments/<int:assignment_id>/submissions/', views.view_submissions, name='view_submissions'),
    path('assignments/', views.student_assignments, name='student_assignments'),
    path('assignment/<int:assignment_id>/history/<int:student_id>/', views.submission_history, name='submission_history'),
    path('submission/<int:submission_id>/approve/', views.approve_submission, name='approve_submission'),
    path('submission/<int:submission_id>/reject/', views.reject_submission, name='reject_submission'),

    # ================= ANNOUNCEMENTS =================
    path('courses/<int:course_id>/announcements/', views.announcement_list, name='announcement_list'),
    path('courses/<int:course_id>/announcements/create/', views.create_announcement, name='create_announcement'),
    path('announcements/', views.global_announcement_list, name='global_announcement_list'),
    path('create/', views.create_announcement, name='create_announcement'),

    # ================= FEEDBACK =================
    path('courses/<int:course_id>/feedback/', views.submit_feedback, name='submit_feedback'),

    # ================= DASHBOARD =================
    path('dashboard/', views.dashboard, name='dashboard'),
    path('courses/category/<int:category_id>/', views.courses_by_category, name='courses_by_category'),

    # ================= FILES & DOWNLOADS =================
    path('lesson/download/<int:lesson_id>/', views.download_lesson_material, name='download_lesson_material'),
    path('downloads/', views.student_downloads, name='student_downloads'),

    # ================= SYSTEM =================
    path('session-check/', views.session_check, name='session_check'),
    path('notifications/', views.notifications, name='notifications'),
    path('pending-classes/', views.pending_classes, name='pending_classes'),

    # ================= PROFILE =================
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),

    # ================= CERTIFICATE =================
    path('finalize-course/<int:enrollment_id>/', views.finalize_course_result, name='finalize_course_result'),
    path('redirect-to-publish/', views.redirect_to_publish, name='redirect_to_publish'),
    path('certificate/<int:enrollment_id>/', views.download_certificate, name='download_certificate'),

    # ================= LEADERBOARD =================
    path('leaderboard/', views.instructor_leaderboard, name='leaderboard'),
    path('instructors/', views.instructors_list, name='instructors_list'),

    # ================= REPORT =================
    path('report/', views.report_general, name='report_general'),
]