from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime
import secrets
import os

app = Flask(__name__, 
            template_folder='templates',  # Explicitly set template folder
            static_folder='.')  # Serve static files from current directory
app.secret_key = secrets.token_hex(16)

# ===== CONFIGURE YOUR EMAIL HERE =====
YOUR_EMAIL = "mecchachameleonstore@gmail.com"  # CHANGE THIS!
YOUR_EMAIL_PASSWORD = "Malapak15."  # CHANGE THIS!
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ===== YOUR PRODUCTS =====
PRODUCTS = {
    "8poses": {
        "id": "8poses",
        "name": "8 Poses Toy Set",
        "price": 34.99,
        "original_price": 49.99,
        "aliexpress_link": "https://nl.aliexpress.com/item/1005012606314092.html"
    },
    "18poses": {
        "id": "18poses",
        "name": "18 Poses Toy Set",
        "price": 49.99,
        "original_price": 66.99,
        "aliexpress_link": "https://nl.aliexpress.com/item/1005012633144316.html"
    }
}

# ===== SERVE CSS AND IMAGES =====
@app.route('/styles.css')
def serve_css():
    return send_from_directory('.', 'styles.css')

@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory('images', filename)

# ===== SEND EMAIL FUNCTION =====
def send_order_email(customer_name, customer_email, customer_address, product, phone=None):
    """Send order details to YOU and confirmation to customer"""
    
    # 1. Email to YOU (with AliExpress link)
    you_subject = f"🛒 NEW ORDER - {product['name']}"
    you_body = f"""
🎉 NEW ORDER RECEIVED!

Product: {product['name']}
Price: €{product['price']}
AliExpress Link: {product['aliexpress_link']}

CUSTOMER DETAILS:
Name: {customer_name}
Email: {customer_email}
Phone: {phone or 'Not provided'}
Address: {customer_address}

---
Order Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Product ID: {product['id']}

⚡ ACTION REQUIRED: 
1. Go to AliExpress link above
2. Add to cart and checkout
3. Ship to customer's address
4. Mark as fulfilled
"""
    
    send_email(YOUR_EMAIL, you_subject, you_body)
    
    # 2. Confirmation to CUSTOMER
    customer_subject = f"✅ Order Confirmation - Mecha Toys"
    customer_body = f"""
Hello {customer_name},

Thank you for your order! We've received it and will process it shortly.

Order Details:
• Product: {product['name']}
• Price: €{product['price']}

Shipping Address:
{customer_address}

What happens next:
1. We'll process your order within 24 hours
2. You'll receive a shipping confirmation with tracking
3. Delivery takes 7-15 business days

Have questions? Just reply to this email!

Thanks for choosing Mecha Toys! 🦎
"""
    
    send_email(customer_email, customer_subject, customer_body)

def send_email(to_email, subject, body):
    """Actually sends the email using SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = YOUR_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(YOUR_EMAIL, YOUR_EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        print(f"Error details: {str(e)}")
        return False

# ===== ROUTES =====
@app.route('/')
def home():
    """Serve your main page"""
    return render_template('index.html', products=PRODUCTS)

@app.route('/checkout/<product_id>')
def checkout(product_id):
    """Show checkout form"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    return render_template('checkout.html', product=product)

@app.route('/place-order', methods=['POST'])
def place_order():
    """Process the order"""
    product_id = request.form.get('product_id')
    customer_name = request.form.get('name')
    customer_email = request.form.get('email')
    customer_phone = request.form.get('phone')
    customer_address = request.form.get('address')
    
    # Validate
    if not all([product_id, customer_name, customer_email, customer_address]):
        return "Please fill in all required fields", 400
    
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    # Create order ID
    order_id = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Save order to file (backup)
    order_data = {
        'order_id': order_id,
        'product': product['name'],
        'product_id': product['id'],
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'customer_address': customer_address,
        'aliexpress_link': product['aliexpress_link'],
        'amount': product['price'],
        'timestamp': datetime.now().isoformat()
    }
    
    # Save to orders.json
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        orders = []
    
    orders.append(order_data)
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)
    
    # Send emails
    send_order_email(
        customer_name, 
        customer_email, 
        customer_address, 
        product,
        customer_phone
    )
    
    return render_template('success.html', order=order_data)

@app.route('/orders')
def view_orders():
    """View all orders (for you only)"""
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
        
        html = """
        <h1>📦 All Orders</h1>
        <table border="1" cellpadding="10" style="border-collapse: collapse; width: 100%;">
            <tr>
                <th>Order ID</th>
                <th>Product</th>
                <th>Customer</th>
                <th>Email</th>
                <th>Amount</th>
                <th>Time</th>
                <th>AliExpress Link</th>
            </tr>
        """
        
        for order in reversed(orders):
            html += f"""
            <tr>
                <td>{order.get('order_id', 'N/A')}</td>
                <td>{order.get('product', 'N/A')}</td>
                <td>{order.get('customer_name', 'N/A')}</td>
                <td>{order.get('customer_email', 'N/A')}</td>
                <td>€{order.get('amount', 0)}</td>
                <td>{order.get('timestamp', 'N/A')[:16]}</td>
                <td><a href="{order.get('aliexpress_link', '#')}" target="_blank">🔗 AliExpress</a></td>
            </tr>
            """
        
        html += "</table><br><a href='/'>← Back to Store</a>"
        return html
        
    except FileNotFoundError:
        return "No orders yet"

if __name__ == '__main__':
    app.run(debug=True, port=5000)

# For Render (expose the app)
application = app