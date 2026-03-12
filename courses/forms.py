from django import forms
from .models import Course, Lesson, Assignment, Submission, Announcement, Profile, Department
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'category', 'difficulty', 'duration_days']
        widgets = {
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'duration_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'e.g. 30'}),
        }

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'content', 'video_url', 'material']


class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        help_text="Password must be at least 8 characters."
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'}),
        help_text="Enter the same password as above for verification."
    )

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'relative_due_days']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
            'relative_due_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. 7',
                'min': '1'
            }),
        }

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.course = course

        self.fields['relative_due_days'].min_value = 1

        if self.course:
            max_days = self.course.duration_days + 5

            self.fields['relative_due_days'].widget.attrs['max'] = max_days
            self.fields['relative_due_days'].help_text = (
                f'Assignment must be due within {max_days} days '
                f'(course duration {self.course.duration_days} + 5 days buffer).'
            )

    def clean_relative_due_days(self):
        relative_due_days = self.cleaned_data.get("relative_due_days")

        if relative_due_days is None:
            return relative_due_days

        if relative_due_days < 1:
            raise forms.ValidationError(
                "Due days must be at least 1."
            )

        if self.course:
            max_days = self.course.duration_days + 5

            if relative_due_days > max_days:
                raise forms.ValidationError(
                    f"Assignment due date cannot exceed {max_days} days."
                )

        return relative_due_days

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['submitted_file']

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'message']
        
class InstructorRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    verification_document = forms.FileField(required=True)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'department', 'verification_document']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile = user.profile
            profile.department = self.cleaned_data['department']
            profile.is_instructor = True
            profile.verification_document = self.cleaned_data['verification_document']
            profile.save()
        return user


class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    year = forms.ChoiceField(
        choices=Profile.YEAR_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'department', 'year']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()
            profile = user.profile
            profile.department = self.cleaned_data['department']
            profile.year = int(self.cleaned_data['year'])
            profile.is_instructor = False
            profile.save()

        return user

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_pic', 'phone', 'department', 'year', 'bio']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.Select(attrs={'class': 'form-select'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'profile_pic': forms.FileInput(attrs={'class': 'd-none'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_pic'].required = False
