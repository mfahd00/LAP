from .models import Category , Enrollment, Announcement

def categories(request):
    return {
        'categories': Category.objects.all()
    }

