from django.contrib import admin
from .models import Course, Lesson, Enrollment, Category, Profile, Department

admin.site.site_header = "LAP Control Panel"
admin.site.site_title = "LAP Admin"
admin.site.index_title = "Welcome to LAP Administration"

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_by', 'created_at', 'category')  

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at')  

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_instructor', 'is_moderator', 'is_approved', 'department')
    list_filter = ('is_instructor', 'department')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')