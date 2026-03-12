from .models import Category , Enrollment, Announcement

def categories(request):
    return {
        'categories': Category.objects.all()
    }

from .models import Notification

def notification_count(request):

    if request.user.is_authenticated:
        unread = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
    else:
        unread = 0

    return {
        "notification_unread_count": unread
    }