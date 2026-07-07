from flask import Flask, render_template, request, send_from_directory, jsonify, session, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime
import secrets
import os

app = Flask(__name__, 
            template_folder='templates',
            static_folder='.')
app.secret_key = secrets.token_hex(16)

# ===== CONFIGURE YOUR EMAIL =====
YOUR_EMAIL = "mecchachameleonstore@gmail.com"
YOUR_EMAIL_PASSWORD = "Malapak15."
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ===== PAYPAL CONFIGURATION =====
PAYPAL_EMAIL = "mecchachameleonstore@gmail.com"  # Tu email de PayPal
PAYPAL_SANDBOX = True  # Cambia a False cuando estés en producción
PAYPAL_URL = "https://www.sandbox.paypal.com/cgi-bin/webscr" if PAYPAL_SANDBOX else "https://www.paypal.com/cgi-bin/webscr"

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
def send_order_email(customer_name, customer_email, customer_address, product, phone=None, order_id=None, txn_id=None):
    """Send order details to YOU and confirmation to customer"""
    
    # 1. Email to YOU
    you_subject = f"🛒 NUEVO PEDIDO - {product['name']}"
    you_body = f"""
🎉 NUEVO PEDIDO RECIBIDO!

ID del Pedido: {order_id or 'N/A'}
Producto: {product['name']}
Precio: €{product['price']}
Método de pago: PayPal
ID Transacción PayPal: {txn_id or 'N/A'}

DATOS DEL CLIENTE:
Nombre: {customer_name}
Email: {customer_email}
Teléfono: {phone or 'No proporcionado'}
Dirección: {customer_address}

---
Hora del pedido: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚡ ACCIÓN REQUERIDA: 
1. PayPal te ha notificado el pago
2. Entra al enlace de AliExpress
3. Añade al carrito y finaliza la compra
4. Envía al cliente a su dirección

ENLACE DE ALIEXPRESS:
{product['aliexpress_link']}
"""
    
    send_email(YOUR_EMAIL, you_subject, you_body)
    
    # 2. Confirmation to CUSTOMER
    customer_subject = f"✅ Confirmación de Pedido - Mecha Toys"
    customer_body = f"""
Hola {customer_name},

¡Gracias por tu pedido! Hemos recibido tu pago correctamente.

Detalles del Pedido:
• Pedido ID: {order_id or 'N/A'}
• Producto: {product['name']}
• Precio: €{product['price']}
• Método de pago: PayPal

Dirección de Envío:
{customer_address}

Próximos pasos:
1. Procesaremos tu pedido en las próximas 24 horas
2. Te enviaremos un email con el número de seguimiento
3. El envío tarda 7-15 días hábiles

¿Preguntas? Responde a este email.

¡Gracias por elegir Mecha Toys! 🦎
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
        return False

# ===== ROUTES =====
@app.route('/')
def home():
    return render_template('index.html', products=PRODUCTS)

@app.route('/checkout/<product_id>', methods=['GET', 'POST'])
def checkout(product_id):
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    if request.method == 'POST':
        # Guardar datos del cliente en la sesión
        session['customer_data'] = {
            'name': request.form.get('name'),
            'email': request.form.get('email'),
            'phone': request.form.get('phone'),
            'address': request.form.get('address'),
            'product_id': product_id
        }
        
        # Construir URL de PayPal con los datos
        customer_data = session['customer_data']
        return_url = f"https://mecha-toys.onrender.com/place-order?product_id={product_id}&name={customer_data['name']}&email={customer_data['email']}&address={customer_data['address']}&phone={customer_data['phone']}"
        
        # Redirigir a PayPal con todos los parámetros
        paypal_form = f"""
        <html>
        <head><title>Redirigiendo a PayPal...</title></head>
        <body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;background:#f5f6fa;">
            <div style="text-align:center;padding:40px;background:white;border-radius:20px;box-shadow:0 10px 40px rgba(0,0,0,0.1);">
                <h2 style="color:#1a1a2e;">🔄 Redirigiendo a PayPal...</h2>
                <p style="color:#636e72;">Por favor, espera un momento.</p>
                <form action="{PAYPAL_URL}" method="post" id="paypal-form">
                    <input type="hidden" name="cmd" value="_xclick">
                    <input type="hidden" name="business" value="{PAYPAL_EMAIL}">
                    <input type="hidden" name="lc" value="ES">
                    <input type="hidden" name="item_name" value="{product['name']}">
                    <input type="hidden" name="amount" value="{product['price']}">
                    <input type="hidden" name="currency_code" value="EUR">
                    <input type="hidden" name="button_subtype" value="services">
                    <input type="hidden" name="no_note" value="0">
                    <input type="hidden" name="tax_rate" value="0.00">
                    <input type="hidden" name="shipping" value="0.00">
                    <input type="hidden" name="return" value="{return_url}">
                    <input type="hidden" name="cancel_return" value="https://mecha-toys.onrender.com/">
                    <button type="submit" style="padding:15px 40px;background:#0070ba;color:white;border:none;border-radius:12px;font-size:1.2rem;cursor:pointer;">Ir a PayPal ahora</button>
                </form>
                <p style="margin-top:20px;color:#636e72;font-size:0.9rem;">Si no eres redirigido automáticamente, haz clic en el botón.</p>
            </div>
            <script>document.getElementById('paypal-form').submit();</script>
        </body>
        </html>
        """
        return paypal_form
    
    # GET: Mostrar formulario de checkout
    return render_template('checkout.html', product=product, paypal_email=PAYPAL_EMAIL)

@app.route('/place-order')
def place_order():
    """Procesa el pedido después del pago con PayPal"""
    
    # Obtener datos de la URL (enviados por PayPal)
    product_id = request.args.get('product_id')
    customer_name = request.args.get('name')
    customer_email = request.args.get('email')
    customer_phone = request.args.get('phone')
    customer_address = request.args.get('address')
    
    # PayPal también envía estos datos adicionales
    payment_status = request.args.get('payment_status')  # 'Completed'
    txn_id = request.args.get('txn_id')  # ID de transacción
    payer_email = request.args.get('payer_email')  # Email del pagador
    
    # Validar que tenemos los datos mínimos necesarios
    if not all([product_id, customer_name, customer_email, customer_address]):
        return """
        <html>
        <head><title>Error - Mecha Toys</title></head>
        <body style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;background:#f5f6fa;">
            <div style="text-align:center;padding:40px;background:white;border-radius:20px;box-shadow:0 10px 40px rgba(0,0,0,0.1);max-width:500px;">
                <h2 style="color:#e17055;">❌ Error en el pedido</h2>
                <p style="color:#636e72;">No se recibieron todos los datos del cliente.</p>
                <p style="color:#636e72;font-size:0.9rem;">Por favor, intenta realizar el pedido de nuevo.</p>
                <a href="/" style="display:inline-block;margin-top:20px;padding:12px 30px;background:#0070ba;color:white;text-decoration:none;border-radius:10px;">Volver a la tienda</a>
            </div>
        </body>
        </html>
        """, 400
    
    # Buscar el producto
    product = PRODUCTS.get(product_id)
    if not product:
        return "Producto no encontrado", 404
    
    # Crear ID de pedido
    order_id = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Guardar pedido
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
        'timestamp': datetime.now().isoformat(),
        'status': 'paid',
        'payment_method': 'paypal',
        'paypal_txn_id': txn_id,
        'paypal_payer_email': payer_email,
        'paypal_status': payment_status
    }
    
    # Guardar en orders.json
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        orders = []
    
    orders.append(order_data)
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)
    
    # Enviar emails
    send_order_email(
        customer_name, 
        customer_email, 
        customer_address, 
        product,
        customer_phone,
        order_id,
        txn_id
    )
    
    # Limpiar sesión
    session.pop('customer_data', None)
    
    # Mostrar página de éxito
    return render_template('success.html', order=order_data)

@app.route('/orders')
def view_orders():
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>📦 Pedidos - Mecha Toys</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: Arial, sans-serif; padding: 40px; background: #f5f6fa; }
                .container { max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); }
                h1 { color: #1a1a2e; margin-bottom: 10px; }
                .total { color: #636e72; margin-bottom: 20px; }
                table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                th { background: #0070ba; color: white; padding: 15px; text-align: left; }
                td { padding: 12px 15px; border-bottom: 1px solid #eee; }
                tr:hover { background: #f8f9fa; }
                .status-paid { color: #00b894; font-weight: 600; }
                .back-link { display: inline-block; margin-top: 20px; padding: 12px 30px; background: #0070ba; color: white; text-decoration: none; border-radius: 10px; }
                .back-link:hover { background: #003087; }
                .no-orders { text-align: center; padding: 60px; color: #636e72; }
                .no-orders h2 { font-size: 2rem; margin-bottom: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📦 Todos los Pedidos</h1>
                <p class="total">Total: <strong>""" + str(len(orders)) + """</strong></p>
        """
        
        if orders:
            html += """
            <table>
                <tr>
                    <th>ID Pedido</th>
                    <th>Producto</th>
                    <th>Cliente</th>
                    <th>Email</th>
                    <th>Total</th>
                    <th>Estado</th>
                    <th>Fecha</th>
                    <th>AliExpress</th>
                </tr>
            """
            
            for order in reversed(orders):
                html += f"""
                <tr>
                    <td><strong>{order.get('order_id', 'N/A')}</strong></td>
                    <td>{order.get('product', 'N/A')}</td>
                    <td>{order.get('customer_name', 'N/A')}</td>
                    <td>{order.get('customer_email', 'N/A')}</td>
                    <td><strong>€{order.get('amount', 0)}</strong></td>
                    <td class="status-paid">✅ PAGADO</td>
                    <td>{order.get('timestamp', 'N/A')[:16]}</td>
                    <td><a href="{order.get('aliexpress_link', '#')}" target="_blank" style="color: #0070ba;">🔗 Comprar</a></td>
                </tr>
                """
            
            html += "</table>"
        else:
            html += """
            <div class="no-orders">
                <h2>📭 No hay pedidos aún</h2>
                <p>Los pedidos aparecerán aquí cuando los clientes compren.</p>
            </div>
            """
        
        html += """
            <a href="/" class="back-link">← Volver a la tienda</a>
            </div>
        </body>
        </html>
        """
        return html
        
    except FileNotFoundError:
        return """
        <div style="text-align:center;padding:60px;">
            <h2>📭 No hay pedidos aún</h2>
            <a href="/" style="display:inline-block;margin-top:20px;padding:12px 30px;background:#0070ba;color:white;text-decoration:none;border-radius:10px;">← Volver a la tienda</a>
        </div>
        """

@app.route('/webhook-paypal', methods=['POST'])
def paypal_webhook():
    """Webhook para recibir notificaciones de PayPal (IPN)"""
    # Por ahora, solo registramos que recibimos algo
    print("📩 Webhook de PayPal recibido")
    return "OK", 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)

application = app