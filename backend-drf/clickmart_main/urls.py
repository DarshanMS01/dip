
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Server-rendered storefront (new shopping experience)
    path('', include('storefront.urls')),
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
    # Serve the original React app for its remaining client-side routes.
    re_path(r'^(?!api/|admin/|static/|media/).*$', TemplateView.as_view(template_name='index.html')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
