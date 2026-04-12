from app import create_app
from app.services.doctor_service import DoctorService

app = create_app()
with app.app_context():
    try:
        doctors = DoctorService.get_all_doctors()
        print(f"Total doctors: {len(doctors)}")
        for d in doctors:
            print(d.to_dict())
    except Exception as e:
        import traceback
        traceback.print_exc()
