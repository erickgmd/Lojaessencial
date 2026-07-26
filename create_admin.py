from app import app, create_admin_from_env

with app.app_context():
    created = create_admin_from_env()
    print("Administrador criado com sucesso." if created else "Esse administrador já existe.")
