from django.urls import path
from .views import get_tables, insert_data, update_data, delete_data, update_multiple, bulk_delete_data, export_table_to_excel, export_multiple, add_annuaire_corrected, import_progress



urlpatterns = [
    path('db/tables/', get_tables, name='get_tables'),
    path('db/annuaires/', add_annuaire_corrected, name='add_annuaire'),
    path('db/annuaires/progress/', import_progress, name='import_progress'),
    path('db/tables/insert', insert_data, name='insert_data'),
    path('db/tables/update/', update_data, name='update_data'),
    path('db/tables/update-multiple/', update_multiple, name='update_multiple'),
    path('db/tables/delete/', delete_data, name='delete_data'),
    path('bulk-delete/', bulk_delete_data, name='bulk_delete_data'),
    path('db/tables/export/', export_table_to_excel, name='export_data'),
    path('db/tables/export-multiple/', export_multiple, name='export_multiple'),

]

