ssh -i my_key.pem ubuntu@107.23.17.237 "ps aux | grep python"from app import app, db, User, Bus, Route, Schedule, BusType
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

def init_database():
    with app.app_context():
        db.create_all()
        
        # Clear existing data
        Schedule.query.delete()
        Bus.query.delete()
        Route.query.delete()
        User.query.delete()
        BusType.query.delete()
        
        # Create bus owners
        owner1 = User(email='owner1@busbooking.com', password=generate_password_hash('password'), 
                     first_name='John', last_name='Operator', phone='9876543210', user_type='owner')
        owner2 = User(email='owner2@busbooking.com', password=generate_password_hash('password'), 
                     first_name='Mike', last_name='Transport', phone='9876543211', user_type='owner')
        owner3 = User(email='owner3@busbooking.com', password=generate_password_hash('password'), 
                     first_name='Sarah', last_name='Travels', phone='9876543212', user_type='owner')
        db.session.add_all([owner1, owner2, owner3])
        db.session.commit()
        
        # Create bus types
        type1 = BusType(name='Non-AC', description='Non Air Conditioned')
        type2 = BusType(name='AC Seater', description='Air Conditioned Seater')
        type3 = BusType(name='AC Sleeper', description='Air Conditioned Sleeper')
        type4 = BusType(name='Recliner', description='Reclining Seats')
        db.session.add_all([type1, type2, type3, type4])
        db.session.commit()
        
        # Add sample buses with owner references
        bus1 = Bus(bus_name='Express Bus', bus_number='BUS001', owner_id=owner1.id, 
                  bus_type_id=type1.id, total_seats=50, amenities='WiFi, USB Charging')
        bus2 = Bus(bus_name='Deluxe Bus', bus_number='BUS002', owner_id=owner2.id, 
                  bus_type_id=type2.id, total_seats=40, amenities='WiFi, Toilet')
        bus3 = Bus(bus_name='Premium Bus', bus_number='BUS003', owner_id=owner3.id, 
                  bus_type_id=type3.id, total_seats=30, amenities='WiFi, Toilet, USB, AC')
        db.session.add_all([bus1, bus2, bus3])
        db.session.commit()
        
        # Add sample routes
        route1 = Route(source='New York', destination='Boston', distance=215)
        route2 = Route(source='Boston', destination='New York', distance=215)
        route3 = Route(source='New York', destination='Philadelphia', distance=95)
        db.session.add_all([route1, route2, route3])
        db.session.commit()
        
        # Add sample schedules
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        
        schedule1 = Schedule(bus_id=bus1.id, route_id=route1.id, journey_date=tomorrow, 
                            departure_time='08:00', arrival_time='14:00', fare=50.0, 
                            available_seats=bus1.total_seats)
        schedule2 = Schedule(bus_id=bus2.id, route_id=route1.id, journey_date=tomorrow, 
                            departure_time='12:00', arrival_time='18:00', fare=60.0,
                            available_seats=bus2.total_seats)
        schedule3 = Schedule(bus_id=bus3.id, route_id=route3.id, journey_date=tomorrow, 
                            departure_time='14:00', arrival_time='16:00', fare=40.0,
                            available_seats=bus3.total_seats)
        db.session.add_all([schedule1, schedule2, schedule3])
        db.session.commit()
        
        print("✓ Database initialized with sample data!")
        print(f"✓ Created 3 bus operators (owners)")
        print(f"✓ Created 4 bus types")
        print(f"✓ Created 3 sample buses")
        print(f"✓ Created 3 sample routes")
        print(f"✓ Created 3 sample schedules")

if __name__ == '__main__':
    init_database()
