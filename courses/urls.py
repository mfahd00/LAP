from django.contrib import admin
from django.urls import path, include
from courses import views as course_views
from . import views

urlpatterns = [
    path('', course_views.home, name='home'),

    # Course-related
    path('courses/', course_views.course_list, name='course_list'),
    path('courses/<int:course_id>/', course_views.course_detail, name='course_detail'),
    path('courses/create/', course_views.create_course, name='create_course'),
    path('courses/<int:course_id>/edit/', course_views.edit_course, name='edit_course'),
    path('courses/<int:course_id>/delete/', course_views.delete_course, name='delete_course'),
    path('courses/<int:course_id>/add_lesson/', course_views.create_lesson, name='create_lesson'),

    # Enrollment (student requests approval)
    path('courses/<int:course_id>/enroll/', course_views.enroll_course, name='enroll_course'),

    # Authentication & Registration
    path('register/', views.choose_registration, name='register'),
    path('register/student/', views.register_student, name='register_student'),
    path('register/instructor/', views.register_instructor, name='register_instructor'),

    path('login/', views.login_page, name='login'),
    path('login/moderator/', views.login_moderator, name='login_moderator'),
    path('login/student/', views.login_student, name='login_student'),
    path('login/instructor/', views.login_instructor, name='login_instructor'),
    path('logout/', views.logout_view, name='logout'),

    # Moderator actions
    path('moderator/instructors/', views.instructors, name='instructors'),
    path('moderator/approve/<int:user_id>/', views.approve_instructor, name='approve_instructor'),
    path('moderator/remove/<int:user_id>/', views.remove_instructor, name='remove_instructor'),
    path('moderator/stats/', views.moderator_stats, name='moderator_stats'),

    # Instructor enrollment management
    path('instructor/enrollments/', views.manage_enrollments, name='manage_enrollments'),
    path('instructor/enrollments/approve/<int:enrollment_id>/', views.approve_enrollment, name='approve_enrollment'),
    path('instructor/enrollments/remove/<int:enrollment_id>/', views.remove_enrollment, name='remove_enrollment'),
    path(
    'instructor/submissions/',
    views.instructor_latest_submissions,
    name='instructor_latest_submissions'
),
    path("student/<int:enrollment_id>/", views.student_detail, name="student_detail"),
    path("student/<int:enrollment_id>/course/",views.student_course_detail,name="student_course_detail"),



    # Dashboard & Misc
    path('dashboard/', views.dashboard, name='dashboard'),
    path('courses/category/<int:category_id>/', views.courses_by_category, name='courses_by_category'),

    # Assignments
    path('courses/<int:course_id>/assignments/', views.assignment_list, name='assignment_list'),
    path('courses/<int:course_id>/assignments/create/', views.create_assignment, name='create_assignment'),
    path('assignments/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
    path('assignments/<int:assignment_id>/submissions/', views.view_submissions, name='view_submissions'),
    path('assignments/', views.student_assignments, name='student_assignments'),
    path("submission/<int:submission_id>/approve/", views.approve_submission, name="approve_submission"),
    path("submission/<int:submission_id>/reject/", views.reject_submission, name="reject_submission"),


    # Pending classes
    path('pending-classes/', views.pending_classes, name='pending_classes'),

    # Announcements
    path('courses/<int:course_id>/announcements/', views.announcement_list, name='announcement_list'),
    path('courses/<int:course_id>/announcements/create/', views.create_announcement, name='create_announcement'),
    path('announcements/', views.global_announcement_list, name='global_announcement_list'),
    path('create/', views.create_announcement, name='create_announcement'),
]
