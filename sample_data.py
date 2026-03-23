from app import app, db, User, BusType, Bus, Route, Schedule
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def create_sample_data():
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        # Create bus types
        bus_types = [
            BusType(name='Non-AC', description='Standard Non-AC seats'),
            BusType(name='AC Seater', description='Air-conditioned seating'),
            BusType(name='AC Sleeper', description='Air-conditioned with sleeper beds'),
            BusType(name='Recliner', description='Luxury recliners with excellent comfort')
        ]
        db.session.add_all(bus_types)
        db.session.commit()

        # Create admin user
        admin = User(
            email='admin@busbooking.com',
            password=generate_password_hash('admin123'),
            first_name='Admin',
            last_name='User',
            phone='9999999999',
            user_type='admin'
        )
        db.session.add(admin)
        db.session.commit()

        # Create 10 customers
        customers = []
        customer_names = [
            ('Rajesh', 'Kumar'), ('Priya', 'Singh'), ('Arjun', 'Patel'),
            ('Divya', 'Sharma'), ('Karan', 'Reddy'), ('Anjali', 'Nair'),
            ('Rohan', 'Desai'), ('Sneha', 'Iyer'), ('Virat', 'Verma'),
            ('Aisha', 'Gupta')
        ]
        for i, (first, last) in enumerate(customer_names):
            customer = User(
                email=f'customer{i+1}@example.com',
                password=generate_password_hash('password123'),
                first_name=first,
                last_name=last,
                phone=f'989999000{i}',
                user_type='customer'
            )
            customers.append(customer)
            db.session.add(customer)
        db.session.commit()

        # Create 10 bus owners
        owners = []
        owner_names = [
            ('VRL', 'Travels'), ('SRS', 'Travels'), ('Sugama', 'Tours'),
            ('Seagull', 'Travels'), ('Orange', 'Tours'), ('Paulo', 'Coelho'),
            ('Shrinivas', 'Express'), ('Kingfisher', 'Travels'), ('Kallada', 'Travels'),
            ('Alankar', 'Express')
        ]
        for i, (first, last) in enumerate(owner_names):
            owner = User(
                email=f'owner{i+1}@example.com',
                password=generate_password_hash('password123'),
                first_name=first,
                last_name=last,
                phone=f'979999000{i}',
                user_type='owner'
            )
            owners.append(owner)
            db.session.add(owner)
        db.session.commit()

        # Create Karnataka cities list
        karnataka_cities = [
            'Bangalore', 'Mysore', 'Belgaum', 'Mangalore', 'Udupi', 'Shimoga',
            'Davangere', 'Tumkur', 'Kolar', 'Chikmagalur', 'Bidar', 'Gulbarga',
            'Chickballapur', 'Raichur', 'Chitradurga', 'Kodagu', 'Uttara Kannada',
            'Hassan', 'Haveri', 'Koppal', 'Mandya', 'Gadag', 'Kurnool',
            'Dharwad', 'Belagavi', 'Yadgir', 'Hassan', 'Channapatna', 'Vellore'
        ]

        # Create 80-100 routes
        routes = []
        route_pairs = []
        for i in range(len(karnataka_cities)):
            for j in range(i+1, len(karnataka_cities)):
                route_pairs.append((karnataka_cities[i], karnataka_cities[j]))
                if len(route_pairs) >= 90:
                    break
            if len(route_pairs) >= 90:
                break

        for source, destination in route_pairs[:90]:
            route = Route(
                source=source,
                destination=destination,
                distance=150 + (hash(source + destination) % 500)
            )
            routes.append(route)
            db.session.add(route)
        db.session.commit()

        # Create 15+ buses per owner (total ~160 buses)
        all_buses = []
        for owner_idx, owner in enumerate(owners):
            bus_type_ids = [1, 2, 3, 4]  # Cycle through bus types
            # Create 16 buses per owner (10 owners * 16 = 160 buses)
            for bus_idx in range(16):
                bus = Bus(
                    bus_number=f'KA-{chr(65 + owner_idx)}{bus_idx + 1:02d}',
                    bus_name=f'{owner_names[owner_idx][0]} Express {bus_idx + 1}',
                    owner_id=owner.id,
                    bus_type_id=bus_type_ids[bus_idx % 4],
                    total_seats=45 + (5 if (bus_idx % 4) < 2 else 0),
                    amenities='WiFi, Charging, Toilet, USB' if (bus_idx % 4) >= 2 else 'Basic Amenities'
                )
                all_buses.append(bus)
                db.session.add(bus)
        db.session.commit()

        # Varied departure times (every 2 hours from 6 AM to 10 PM)
        departure_times = [
            '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'
        ]
        
        # Create schedules: Every route needs minimum 15 buses per day for 30 days
        buses = Bus.query.all()
        today = datetime.now().date()

        schedule_count = 0
        for route in routes:  # For every route
            for day_offset in range(30):  # For 30 days
                journey_date = today + timedelta(days=day_offset)
                
                # Assign 15+ different buses to this route on this day
                for bus_idx in range(15):
                    bus = buses[(hash(route.id + day_offset + bus_idx) % len(buses))]
                    
                    # Vary departure times
                    dep_time_str = departure_times[bus_idx % len(departure_times)]
                    dep_hour, dep_minute = map(int, dep_time_str.split(':'))
                    
                    # Calculate arrival time (12 hours later)
                    arr_hour = (dep_hour + 12) % 24
                    arr_time_str = f'{arr_hour:02d}:00'
                    
                    # Vary fare based on bus type and time
                    base_fare = 400 + (route.distance // 3)
                    time_multiplier = 1 + (bus_idx % 3) * 0.1  # Vary by 10-20%
                    fare = int(base_fare * time_multiplier)
                    
                    schedule = Schedule(
                        bus_id=bus.id,
                        route_id=route.id,
                        journey_date=journey_date,
                        departure_time=datetime.strptime(dep_time_str, '%H:%M').time(),
                        arrival_time=datetime.strptime(arr_time_str, '%H:%M').time(),
                        fare=fare,
                        available_seats=bus.total_seats
                    )
                    db.session.add(schedule)
                    schedule_count += 1
        
        db.session.commit()
        print(f"Sample data created successfully!")
        print(f"✓ Routes: {len(routes)}")
        print(f"✓ Buses: {len(all_buses)}")
        print(f"✓ Schedules: {schedule_count} (15+ per route, daily for 30 days)")
        print(f"✓ Bus companies: 10 (repeating with different departure times)")

if __name__ == '__main__':
    create_sample_data()
