from django.urls import path

from .views import OutputsView, RenderView

urlpatterns = [
    path('projects/<uuid:project_id>/outputs/', OutputsView.as_view(), name='outputs'),
    path('projects/<uuid:project_id>/render/', RenderView.as_view({'post': 'create'}), name='render'),
]
