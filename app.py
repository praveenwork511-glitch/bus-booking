from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from io import BytesIO
from dotenv import load_dotenv
import stripe
from backend.s3_helpers import register_s3_context

# Load environment variables
load_dotenv()

try:
    from twilio.rest import Client
except ImportError:
    Client = None  # Twilio optional for SMS
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
except ImportError:
    pass  # ReportLab optional for PDF generation

app = Flask(__name__, 
            static_folder='backend/static', 
            template_folder='backend/templates')
# Use PostgreSQL from .env if available, else SQLite for development
database_url = os.getenv('DATABASE_URL')
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///busbooking.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')

# Stripe Configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', 'sk_test_placeholder_change_in_production')  # Test key - change in production
STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', 'pk_test_placeholder_change_in_production')  # Test key - change in production

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'your_account_sid')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', 'your_auth_token')
TWILIO_PHONE = os.environ.get('TWILIO_PHONE', '+1234567890')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Register S3 URL helper with Flask templates
register_s3_context(app)

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # customer, owner, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BusType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # AC, Non-AC, Sleeper, Recliner
    description = db.Column(db.String(255))

class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(50), nullable=False, unique=True)
    bus_name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bus_type_id = db.Column(db.Integer, db.ForeignKey('bus_type.id'), nullable=False)
    total_seats = db.Column(db.Integer, nullable=False)
    amenities = db.Column(db.String(500))
    photo_filename = db.Column(db.String(255), nullable=True)  # Store photo filename
    owner = db.relationship('User', backref='buses')
    bus_type = db.relationship('BusType', backref='buses')

class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(100), nullable=False)
    distance = db.Column(db.Float)

class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    station_name = db.Column(db.String(100), nullable=False)
    station_code = db.Column(db.String(10), unique=True, nullable=False)
    is_boarding = db.Column(db.Boolean, default=True)
    is_dropping = db.Column(db.Boolean, default=True)
    
class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    journey_date = db.Column(db.Date, nullable=False)
    departure_time = db.Column(db.Time, nullable=False)
    arrival_time = db.Column(db.Time)
    fare = db.Column(db.Float, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    days_of_week = db.Column(db.String(50), nullable=True)  # Comma-separated: 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
    bus = db.relationship('Bus', backref='schedules')
    route = db.relationship('Route', backref='schedules')

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=False)
    seat_number = db.Column(db.String(10), nullable=False)
    passenger_name = db.Column(db.String(100), nullable=False)
    passenger_phone = db.Column(db.String(15), nullable=False)
    boarding_station = db.Column(db.String(100), nullable=True)
    dropping_station = db.Column(db.String(100), nullable=True)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='confirmed')  # confirmed, cancelled, completed
    total_fare = db.Column(db.Float, nullable=False)
    customer = db.relationship('User', backref='bookings')
    schedule = db.relationship('Schedule', backref='bookings')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))  # card, upi, net_banking
    payment_status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    transaction_id = db.Column(db.String(100))
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    booking = db.relationship('Booking', backref='payments')

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    notification_type = db.Column(db.String(20))  # sms, email
    phone_number = db.Column(db.String(15), nullable=False)
    message = db.Column(db.Text)
    sent_status = db.Column(db.String(20), default='pending')  # pending, sent, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    booking = db.relationship('Booking', backref='notifications')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# HELPER FUNCTIONS
def send_sms(phone_number, message):
    """Send SMS notification using Twilio"""
    try:
        if Client is None:
            # Twilio not installed, just log the message
            print(f"SMS to {phone_number}: {message}")
            return False
        
        # Initialize Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Send SMS
        message = client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=phone_number
        )
        
        return True
    except Exception as e:
        print(f"Failed to send SMS: {str(e)}")
        return False

# ROUTES
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.user_type == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.user_type == 'owner':
            return redirect(url_for('owner_dashboard'))
        else:
            return redirect(url_for('customer_dashboard'))
    
    # Fetch today's routes with bus count
    today = datetime.now().date()
    routes_today = []
    routes = Route.query.all()
    
    for route in routes:
        schedule_count = Schedule.query.filter(
            Schedule.route_id == route.id, 
            Schedule.journey_date == today
        ).count()
        
        if schedule_count > 0:
            bus_count = Bus.query.join(Schedule).filter(
                Schedule.route_id == route.id,
                Schedule.journey_date == today
            ).distinct(Bus.id).count()
            
            routes_today.append({
                'id': route.id,
                'source': route.source,
                'destination': route.destination,
                'distance': route.distance,
                'bus_count': bus_count,
                'schedule_count': schedule_count
            })
    
    return render_template('index.html', routes_today=routes_today)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form['phone']
        user_type = request.form['user_type']

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('register'))

        user = User(
            email=email,
            password=generate_password_hash(password),
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            user_type=user_type
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            # Redirect to next page if provided (e.g., from @login_required)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.user_type == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.user_type == 'owner':
                return redirect(url_for('owner_dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid email or password', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    routes = Route.query.all()
    schedules = []

    if request.method == 'POST':
        source = request.form['source']
        destination = request.form['destination']
        journey_date = request.form['journey_date']

        schedules = db.session.query(Schedule, Bus, Route, BusType).join(Bus, Schedule.bus_id == Bus.id)\
            .join(Route, Schedule.route_id == Route.id)\
            .join(BusType, Bus.bus_type_id == BusType.id)\
            .filter(Route.source.ilike(source), Route.destination.ilike(destination), 
                    Schedule.journey_date == datetime.strptime(journey_date, '%Y-%m-%d').date()).all()

    return render_template('search.html', routes=routes, schedules=schedules)

@app.route('/book/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def book(schedule_id):
    schedule = Schedule.query.get(schedule_id)
    bus = Bus.query.get(schedule.bus_id)
    route = Route.query.get(schedule.route_id)

    if request.method == 'POST':
        passenger_name = request.form['passenger_name']
        passenger_phone = request.form['passenger_phone']
        seat_number = request.form['seat_number']

        existing = Booking.query.filter_by(schedule_id=schedule_id, seat_number=seat_number).first()
        if existing:
            flash('Seat already booked', 'error')
            return redirect(url_for('book', schedule_id=schedule_id))

        booking = Booking(
            customer_id=current_user.id,
            schedule_id=schedule_id,
            seat_number=seat_number,
            passenger_name=passenger_name,
            passenger_phone=passenger_phone,
            total_fare=schedule.fare
        )
        db.session.add(booking)
        db.session.commit()

        return redirect(url_for('payment', booking_id=booking.id))

    booked_seats = Booking.query.filter_by(schedule_id=schedule_id).all()
    booked_seat_numbers = [b.seat_number for b in booked_seats]

    return render_template('book.html', schedule=schedule, bus=bus, route=route, 
                         booked_seats=booked_seat_numbers)

@app.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def payment(booking_id):
    booking = Booking.query.get(booking_id)
    
    if not booking or booking.customer_id != current_user.id:
        flash('Booking not found.', 'danger')
        return redirect(url_for('search'))
    
    if request.method == 'POST':
        try:
            # Create a Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[
                    {
                        'price_data': {
                            'currency': 'inr',
                            'unit_amount': int(booking.total_fare * 100),  # Convert to paise
                            'product_data': {
                                'name': f"Bus Booking - {booking.schedule.route.source} to {booking.schedule.route.destination}",
                                'description': f"Booking ID: {booking.id}",
                            },
                        },
                        'quantity': 1,
                    }
                ],
                mode='payment',
                success_url=url_for('booking_confirmation', booking_id=booking_id, _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=url_for('payment', booking_id=booking_id, _external=True),
            )
            
            return redirect(checkout_session.url, code=303)
        except stripe.error.StripeError as e:
            flash(f'Payment error: {str(e)}', 'danger')
            return redirect(url_for('payment', booking_id=booking_id))
    
    return render_template('payment.html', booking=booking, stripe_public_key=STRIPE_PUBLIC_KEY)

@app.route('/booking-confirmation/<int:booking_id>')
@login_required
def booking_confirmation(booking_id):
    booking = Booking.query.get(booking_id)
    
    if not booking or booking.customer_id != current_user.id:
        flash('Booking not found.', 'danger')
        return redirect(url_for('search'))
    
    # Handle Stripe payment confirmation
    session_id = request.args.get('session_id')
    if session_id and booking.status != 'confirmed':
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            if checkout_session.payment_status == 'paid':
                # Create payment record
                payment = Payment(
                    booking_id=booking_id,
                    amount=booking.total_fare,
                    payment_method='card',
                    payment_status='completed'
                )
                db.session.add(payment)
                booking.status = 'confirmed'
                db.session.commit()
                
                # Send SMS confirmation
                sms_message = f"✅ Booking Confirmed! Ticket ID: {booking.id}\n{booking.schedule.route.source} → {booking.schedule.route.destination}\nDate: {booking.schedule.journey_date}\nSeat: {booking.seat_number}\nThank you!"
                send_sms(booking.passenger_phone, sms_message)
                
                flash('Booking confirmed! Payment successful. SMS sent to your phone.', 'success')
        except stripe.error.StripeError as e:
            flash(f'Payment verification error: {str(e)}', 'danger')
    
    return render_template('booking_confirmation.html', booking=booking)

@app.route('/download-ticket/<int:booking_id>')
@login_required
def download_ticket(booking_id):
    booking = Booking.query.get(booking_id)
    
    if not booking or booking.customer_id != current_user.id:
        flash('Booking not found.', 'danger')
        return redirect(url_for('search'))
    
    try:
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Custom style for title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#ff006e'),
            alignment=1,
            spaceAfter=20
        )
        
        # Build content
        elements = []
        elements.append(Paragraph("🎫 Bus Ticket Confirmation", title_style))
        elements.append(Spacer(1, 0.3*inch))
        
        # Booking Details Table
        data = [
            ['Booking ID:', str(booking.id)],
            ['Passenger Name:', booking.passenger_name],
            ['Route:', f"{booking.schedule.route.source} → {booking.schedule.route.destination}"],
            ['Date:', str(booking.schedule.journey_date)],
            ['Departure:', str(booking.schedule.departure_time)],
            ['Arrival:', str(booking.schedule.arrival_time)],
            ['Seat Number:', str(booking.seat_number)],
            ['Boarding Station:', booking.boarding_station or 'N/A'],
            ['Dropping Station:', booking.dropping_station or 'N/A'],
            ['Total Fare:', f"₹{booking.total_fare}"],
            ['Status:', booking.status.upper()],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#00d4ff')),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("Thank you for booking with us! Safe travels!", styles['Normal']))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"ticket_{booking.id}.pdf"
        )
    except Exception as e:
        flash(f'Error generating ticket: {str(e)}', 'danger')
        return redirect(url_for('customer_dashboard'))

@app.route('/customer-dashboard')
@login_required
def customer_dashboard():
    if current_user.user_type != 'customer':
        return redirect(url_for('home'))

    upcoming_bookings = db.session.query(Booking, Schedule, Bus, Route).join(
        Schedule, Booking.schedule_id == Schedule.id).join(
        Bus, Schedule.bus_id == Bus.id).join(
        Route, Schedule.route_id == Route.id).filter(
        Booking.customer_id == current_user.id,
        Schedule.journey_date >= datetime.now().date()).all()

    past_bookings = db.session.query(Booking, Schedule, Bus, Route).join(
        Schedule, Booking.schedule_id == Schedule.id).join(
        Bus, Schedule.bus_id == Bus.id).join(
        Route, Schedule.route_id == Route.id).filter(
        Booking.customer_id == current_user.id,
        Schedule.journey_date < datetime.now().date()).all()

    return render_template('customer_dashboard.html', 
                         upcoming_bookings=upcoming_bookings,
                         past_bookings=past_bookings)

@app.route('/owner-dashboard')
@login_required
def owner_dashboard():
    if current_user.user_type != 'owner':
        return redirect(url_for('home'))

    buses = Bus.query.filter_by(owner_id=current_user.id).all()
    routes = Route.query.all()
    return render_template('owner_dashboard.html', buses=buses, routes=routes)
@app.route('/api/init-routes', methods=['POST'])
@login_required
def init_routes():
    """Initialize sample routes and bus types if none exist"""
    if current_user.user_type != 'admin' and current_user.user_type != 'owner':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Create bus types if they don't exist
    existing_types = BusType.query.count()
    if existing_types == 0:
        bus_types = [
            BusType(name='Non-AC', description='Standard Non-AC seats'),
            BusType(name='AC Seater', description='Air-conditioned seating'),
            BusType(name='AC Sleeper', description='Air-conditioned with sleeper beds'),
            BusType(name='Recliner', description='Luxury recliners')
        ]
        db.session.add_all(bus_types)
        db.session.commit()
    
    # Check if routes already exist
    existing_routes = Route.query.count()
    if existing_routes > 0:
        return jsonify({'success': True, 'message': f'{existing_routes} routes already exist'}), 200
    
    # Create sample routes between major Indian cities
    sample_routes = [
        ('Bangalore', 'Mysore', 150),
        ('Bangalore', 'Mangalore', 350),
        ('Bangalore', 'Belgaum', 280),
        ('Bangalore', 'Udupi', 420),
        ('Bangalore', 'Shimoga', 250),
        ('Mysore', 'Mangalore', 380),
        ('Mysore', 'Belgaum', 280),
        ('Mysore', 'Hassan', 120),
        ('Mangalore', 'Udupi', 100),
        ('Mangalore', 'Belgaum', 450),
        ('Hassan', 'Shimoga', 180),
        ('Belgaum', 'Bidar', 200),
        ('Shimoga', 'Chikmagalur', 150),
        ('Bangalore', 'Hyderabad', 600),
        ('Bangalore', 'Chennai', 350),
        ('Bangalore', 'Coimbatore', 400),
        ('Bangalore', 'Salem', 320),
        ('Bangalore', 'Kolar', 80),
        ('Bangalore', 'Tumkur', 70),
        ('Bangalore', 'Chikmagalur', 220),
    ]
    
    for source, destination, distance in sample_routes:
        route = Route(source=source, destination=destination, distance=distance)
        db.session.add(route)
    
    db.session.commit()
    return jsonify({'success': True, 'message': f'{len(sample_routes)} routes created successfully'}), 201
@app.route('/api/add-bus', methods=['POST'])
@login_required
def add_bus():
    """Add a new bus for the owner"""
    if current_user.user_type != 'owner':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    bus_number = data.get('bus_number')
    bus_name = data.get('bus_name')
    bus_type_id = data.get('bus_type_id')
    total_seats = data.get('total_seats')
    amenities = data.get('amenities', '')
    
    # Validate required fields
    if not all([bus_number, bus_name, bus_type_id, total_seats]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if bus number already exists
    if Bus.query.filter_by(bus_number=bus_number).first():
        return jsonify({'error': 'Bus number already exists'}), 400
    
    try:
        total_seats = int(total_seats)
        if total_seats <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid total seats'}), 400
    
    bus = Bus(
        bus_number=bus_number,
        bus_name=bus_name,
        owner_id=current_user.id,
        bus_type_id=int(bus_type_id),
        total_seats=total_seats,
        amenities=amenities
    )
    
    db.session.add(bus)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'bus_id': bus.id,
        'message': f'Bus "{bus_name}" added successfully!'
    }), 201

@app.route('/api/upload-bus-photo/<int:bus_id>', methods=['POST'])
@login_required
def upload_bus_photo(bus_id):
    """Upload photo for a bus"""
    bus = Bus.query.get_or_404(bus_id)
    
    # Verify ownership
    if bus.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo provided'}), 400
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        # Generate unique filename
        filename = f"bus_{bus_id}_{datetime.utcnow().timestamp()}.jpg"
        upload_dir = 'static/bus_photos'
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        
        # Save file
        file.save(filepath)
        
        # Update bus record
        bus.photo_filename = filename
        db.session.commit()
        
        return jsonify({'success': True, 'photo_url': f'/static/bus_photos/{filename}'}), 200
    
    return jsonify({'error': 'Invalid file format'}), 400

@app.route('/api/add-schedule', methods=['POST'])
@login_required
def add_schedule():
    """Add or update a bus schedule"""
    data = request.get_json()
    bus_id = data.get('bus_id')
    route_id = data.get('route_id')
    departure_time = data.get('departure_time')
    arrival_time = data.get('arrival_time')
    fare = data.get('fare')
    days_of_week = data.get('days_of_week')  # e.g., "Mon,Tue,Wed,Thu,Fri,Sat,Sun"
    
    # Verify bus ownership
    bus = Bus.query.get_or_404(bus_id)
    if bus.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    route = Route.query.get_or_404(route_id)
    
    # Create schedule for today (will repeat based on days_of_week)
    try:
        from datetime import time
        dep_time = datetime.strptime(departure_time, '%H:%M').time()
        arr_time = datetime.strptime(arrival_time, '%H:%M').time() if arrival_time else None
        fare_float = float(fare)
    except ValueError:
        return jsonify({'error': 'Invalid time or fare format'}), 400
    
    schedule = Schedule(
        bus_id=bus_id,
        route_id=route_id,
        journey_date=datetime.utcnow().date(),
        departure_time=dep_time,
        arrival_time=arr_time,
        fare=fare_float,
        available_seats=bus.total_seats,
        days_of_week=days_of_week
    )
    
    db.session.add(schedule)
    db.session.commit()
    
    return jsonify({'success': True, 'schedule_id': schedule.id}), 201

@app.route('/api/delete-schedule/<int:schedule_id>', methods=['DELETE'])
@login_required
def delete_schedule(schedule_id):
    """Delete a bus schedule"""
    schedule = Schedule.query.get_or_404(schedule_id)
    bus = schedule.bus
    
    if bus.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(schedule)
    db.session.commit()
    
    return jsonify({'success': True}), 200

@app.route('/api/routes', methods=['GET'])
def get_routes():
    """Get all available routes"""
    routes = Route.query.all()
    return jsonify([{
        'id': r.id,
        'source': r.source,
        'destination': r.destination,
        'distance': r.distance
    } for r in routes]), 200

@app.route('/api/bus-schedules/<int:bus_id>', methods=['GET'])
@login_required
def get_bus_schedules(bus_id):
    """Get all schedules for a specific bus"""
    bus = Bus.query.get_or_404(bus_id)
    
    # Verify ownership
    if bus.owner_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    schedules = Schedule.query.filter_by(bus_id=bus_id).all()
    
    return jsonify([{
        'id': s.id,
        'route_id': s.route_id,
        'route_name': f"{s.route.source} → {s.route.destination}",
        'departure_time': s.departure_time.strftime('%H:%M'),
        'arrival_time': s.arrival_time.strftime('%H:%M') if s.arrival_time else '',
        'fare': s.fare,
        'days_of_week': s.days_of_week,
        'available_seats': s.available_seats
    } for s in schedules]), 200

@app.route('/admin-dashboard')
@login_required
def admin_dashboard():
    if current_user.user_type != 'admin':
        return redirect(url_for('home'))

    total_users = User.query.count()
    total_bookings = Booking.query.count()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(payment_status='completed').scalar() or 0

    return render_template('admin_dashboard.html', 
                         total_users=total_users,
                         total_bookings=total_bookings,
                         total_revenue=total_revenue)

@app.route('/admin/buses')
@login_required
def admin_buses():
    if current_user.user_type != 'admin':
        return redirect(url_for('home'))

    today = datetime.now().date()
    
    # Query routes with bus count and schedule count
    routes_list = []
    routes = Route.query.all()
    
    for route in routes:
        bus_count = Bus.query.join(Schedule).filter(Schedule.route_id == route.id).distinct(Bus.id).count()
        schedule_count = Schedule.query.filter(Schedule.route_id == route.id, Schedule.journey_date == today).count()
        booking_count = Booking.query.join(Schedule).filter(Schedule.route_id == route.id).count()
        revenue = db.session.query(db.func.sum(Payment.amount)).join(Booking).join(Schedule)\
                  .filter(Schedule.route_id == route.id, Payment.payment_status == 'completed').scalar() or 0
        
        routes_list.append({
            'id': route.id,
            'source': route.source,
            'destination': route.destination,
            'distance': route.distance,
            'bus_count': bus_count,
            'schedule_count': schedule_count,
            'booking_count': booking_count,
            'revenue': revenue
        })

    return render_template('admin_buses.html', routes_list=routes_list)

@app.route('/bus-tracking', methods=['GET', 'POST'])
def bus_tracking():
    bus_info = None
    schedules = None
    
    if request.method == 'POST':
        bus_number = request.form.get('bus_number', '').upper()
        bus = Bus.query.filter_by(bus_number=bus_number).first()
        
        if bus:
            today = datetime.now().date()
            bus_info = {
                'id': bus.id,
                'number': bus.bus_number,
                'name': bus.bus_name,
                'type': BusType.query.get(bus.bus_type_id).name,
                'owner': User.query.get(bus.owner_id).first_name,
                'total_seats': bus.total_seats,
                'amenities': bus.amenities
            }
            
            schedules = db.session.query(Schedule, Route)\
                .join(Route, Schedule.route_id == Route.id)\
                .filter(Schedule.bus_id == bus.id, Schedule.journey_date == today)\
                .all()
    
    return render_template('bus_tracking.html', bus_info=bus_info, schedules=schedules)

@app.route('/api/bus-location/<int:bus_id>')
def api_bus_location(bus_id):
    bus = Bus.query.get(bus_id)
    if not bus:
        return {'error': 'Bus not found'}, 404
    
    # Simulate bus location based on bus ID and current time
    import math
    base_lat = 12.9716  # Bangalore
    base_lng = 77.5946
    
    # Generate pseudo-random but deterministic location based on time
    now = datetime.now()
    offset = (bus_id + now.hour + now.minute) % 360
    
    lat = base_lat + (math.sin(math.radians(offset)) * 0.5)
    lng = base_lng + (math.cos(math.radians(offset)) * 0.5)
    
    return {
        'bus_number': bus.bus_number,
        'lat': lat,
        'lng': lng,
        'speed': 60 + (bus_id % 40),
        'status': 'On Route',
        'timestamp': datetime.now().isoformat()
    }

if __name__ == '__main__':
    from your_app import app, db

    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
