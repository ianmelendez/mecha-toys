from flask import Flask, render_template, request, send_from_directory, jsonify, session, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime
import secrets
import os
import uuid
import paypalrestsdk  # NUEVA IMPORTACIÓN

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
PAYPAL_EMAIL = "mecchachameleonstore@gmail.com"
PAYPAL_SANDBOX = False
PAYPAL_URL = "https://www.paypal.com/cgi-bin/webscr"

# ===== PAYPAL API CONFIGURATION (para Apple Pay) =====
PAYPAL_CLIENT_ID = "ARlmoa47tt-GIkbslRohxq74lrNmv7kdpo6TTk4WYzS4DkZ5VqAk1CjVDzoaCHOHeFYcy_UQdWw2OqKj"
PAYPAL_CLIENT_SECRET = "EDQ2PE-NJO4IQoivFo9_EiAiKm-LH9B5CKWAxnwAadambd5KbxaVsY9Gh3_6axdlJbDtOF84p2fqBJa4"
PAYPAL_MODE = "live"  # "sandbox" para pruebas

# Configurar PayPal SDK
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET
})

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

# ===== APPLE PAY DOMAIN VERIFICATION =====
@app.route('/.well-known/apple-developer-merchantid-domain-association')
def serve_apple_pay():
    """Serve Apple Pay domain verification file"""
    try:
        return send_from_directory('.', 'apple-developer-merchantid-domain-association')
    except Exception as e:
        print(f"Error serving Apple Pay verification: {e}")
        return "File not found", 404

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

@app.route('/checkout/<product_id>', methods=['GET'])
def checkout(product_id):
    """Mostrar checkout con PayPal y Apple Pay"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    return render_template('checkout_with_applepay.html', 
                         product=product,
                         client_id=PAYPAL_CLIENT_ID,
                         paypal_email=PAYPAL_EMAIL,
                         paypal_url=PAYPAL_URL)

@app.route('/checkout/<product_id>', methods=['POST'])
def process_checkout(product_id):
    """Procesar el checkout (PayPal Standard)"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    # Obtener datos del formulario
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone', '')
    address = request.form.get('address')
    
    if not all([name, email, address]):
        return "Faltan datos requeridos", 400
    
    # Guardar en sesión
    session['customer_data'] = {
        'name': name,
        'email': email,
        'phone': phone,
        'address': address,
        'product_id': product_id
    }
    
    # Redirigir a PayPal
    return redirect(url_for('paypal_redirect', product_id=product_id))

@app.route('/paypal-redirect/<product_id>')
def paypal_redirect(product_id):
    """Redirigir a PayPal para pago estándar"""
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    customer_data = session.get('customer_data', {})
    
    return_url = f"https://mecha-toys.onrender.com/place-order?product_id={product_id}&name={customer_data.get('name')}&email={customer_data.get('email')}&address={customer_data.get('address')}&phone={customer_data.get('phone')}"
    
    paypal_form = f"""
    <!DOCTYPE html>
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
                <input type="hidden" name="no_note" value="1">
                <input type="hidden" name="tax_rate" value="0.00">
                <input type="hidden" name="shipping" value="0.00">
                <input type="hidden" name="return" value="{return_url}">
                <input type="hidden" name="cancel_return" value="https://mecha-toys.onrender.com/">
            </form>
            <button onclick="document.getElementById('paypal-form').submit()" style="padding:15px 40px;background:#0070ba;color:white;border:none;border-radius:12px;font-size:1.2rem;cursor:pointer;">Ir a PayPal</button>
        </div>
    </body>
    </html>
    """
    return paypal_form

# ===== NUEVA RUTA PARA APPLE PAY =====
@app.route('/create-apple-pay-order', methods=['POST'])
def create_apple_pay_order():
    """Crear un pedido para Apple Pay"""
    try:
        data = request.json
        product_id = data.get('product_id')
        customer_name = data.get('customer_name')
        customer_email = data.get('customer_email')
        customer_phone = data.get('customer_phone', '')
        customer_address = data.get('customer_address')
        
        if not all([product_id, customer_name, customer_email, customer_address]):
            return jsonify({'error': 'Faltan datos requeridos'}), 400
        
        product = PRODUCTS.get(product_id)
        if not product:
            return jsonify({'error': 'Producto no encontrado'}), 404
        
        # Guardar datos del cliente en sesión
        session['customer_data'] = {
            'name': customer_name,
            'email': customer_email,
            'phone': customer_phone,
            'address': customer_address,
            'product_id': product_id
        }
        
        # Crear pedido en PayPal
        order = paypalrestsdk.Order({
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "description": product['name'],
                "amount": {
                    "currency_code": "EUR",
                    "value": str(product['price'])
                }
            }],
            "application_context": {
                "return_url": "https://mecha-toys.onrender.com/payment-success",
                "cancel_url": "https://mecha-toys.onrender.com/payment-cancel",
                "user_action": "PAY_NOW"
            }
        })
        
        if order.create():
            return jsonify({
                'order_id': order.id,
                'status': 'created'
            })
        else:
            return jsonify({'error': order.error}), 400
            
    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({'error': str(e)}), 500

# ===== NUEVA RUTA PARA CAPTURAR PAGO DE APPLE PAY =====
@app.route('/capture-apple-pay-order', methods=['POST'])
def capture_apple_pay_order():
    """Capturar el pago después de Apple Pay"""
    try:
        data = request.json
        order_id = data.get('order_id')
        
        if not order_id:
            return jsonify({'error': 'Order ID requerido'}), 400
        
        # Capturar el pago
        order = paypalrestsdk.Order.find(order_id)
        
        if order.capture():
            # Pago capturado exitosamente
            transaction_id = order.purchase_units[0].payments.captures[0].id
            
            # Obtener datos del cliente de la sesión
            customer_data = session.get('customer_data', {})
            
            product_id = customer_data.get('product_id')
            product = PRODUCTS.get(product_id)
            
            if product:
                # Crear ID de pedido
                order_id_internal = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Guardar pedido
                order_data = {
                    'order_id': order_id_internal,
                    'product': product['name'],
                    'product_id': product['id'],
                    'customer_name': customer_data.get('name'),
                    'customer_email': customer_data.get('email'),
                    'customer_phone': customer_data.get('phone', ''),
                    'customer_address': customer_data.get('address'),
                    'aliexpress_link': product['aliexpress_link'],
                    'amount': product['price'],
                    'timestamp': datetime.now().isoformat(),
                    'status': 'paid',
                    'payment_method': 'apple_pay',
                    'paypal_transaction_id': transaction_id,
                    'paypal_order_id': order_id
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
                    customer_data.get('name'),
                    customer_data.get('email'),
                    customer_data.get('address'),
                    product,
                    customer_data.get('phone'),
                    order_id_internal,
                    transaction_id
                )
            
            # Limpiar sesión
            session.pop('customer_data', None)
            
            return jsonify({
                'success': True,
                'transaction_id': transaction_id
            })
        else:
            return jsonify({'error': 'Error al capturar el pago'}), 400
            
    except Exception as e:
        print(f"Error capturing order: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/place-order')
def place_order():
    """Procesa el pedido después del pago con PayPal Standard"""
    product_id = request.args.get('product_id')
    customer_name = request.args.get('name')
    customer_email = request.args.get('email')
    customer_phone = request.args.get('phone')
    customer_address = request.args.get('address')
    
    # PayPal también envía estos datos adicionales
    payment_status = request.args.get('payment_status')
    txn_id = request.args.get('txn_id')
    payer_email = request.args.get('payer_email')
    
    if not all([product_id, customer_name, customer_email, customer_address]):
        return "Faltan datos del cliente", 400
    
    product = PRODUCTS.get(product_id)
    if not product:
        return "Producto no encontrado", 404
    
    order_id = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
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
        'status': 'paid' if payment_status == 'Completed' else 'pending',
        'payment_method': 'paypal_standard',
        'paypal_txn_id': txn_id,
        'paypal_payer_email': payer_email,
        'paypal_status': payment_status
    }
    
    try:
        with open('orders.json', 'r') as f:
            orders = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        orders = []
    
    orders.append(order_data)
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)
    
    send_order_email(
        customer_name,
        customer_email,
        customer_address,
        product,
        customer_phone,
        order_id,
        txn_id
    )
    
    session.pop('customer_data', None)
    
    return render_template('success.html', order=order_data)

@app.route('/payment-success')
def payment_success():
    """Página de éxito para Apple Pay"""
    return redirect('/orders')

@app.route('/payment-cancel')
def payment_cancel():
    """Página de cancelación"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Pago Cancelado - Mecha Toys</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            padding: 50px;
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 500px;
        }
        h2 { color: #fdcb6e; margin-bottom: 10px; }
        .btn {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 30px;
            background: #0070ba;
            color: white;
            text-decoration: none;
            border-radius: 10px;
        }
    </style>
    </head>
    <body>
        <div class="container">
            <h2>⚠️ Pago Cancelado</h2>
            <p>Tu pago fue cancelado. No se realizaron cargos.</p>
            <a href="/" class="btn">← Volver a la tienda</a>
        </div>
    </body>
    </html>
    """

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
                body { font-family: 'Inter', sans-serif; padding: 40px; background: #f5f6fa; }
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
                    <th>Método</th>
                    <th>Cliente</th>
                    <th>Total</th>
                    <th>Estado</th>
                    <th>Fecha</th>
                </tr>
            """
            
            for order in reversed(orders):
                status_color = "status-paid" if order.get('status') == 'paid' else ""
                status_text = "✅ PAGADO" if order.get('status') == 'paid' else "⏳ PENDIENTE"
                method = order.get('payment_method', 'paypal_standard')
                method_icon = "🍎" if method == "apple_pay" else "💳"
                html += f"""
                <tr>
                    <td><strong>{order.get('order_id', 'N/A')}</strong></td>
                    <td>{order.get('product', 'N/A')}</td>
                    <td>{method_icon} {method.replace('_', ' ').title()}</td>
                    <td>{order.get('customer_name', 'N/A')}</td>
                    <td><strong>€{order.get('amount', 0)}</strong></td>
                    <td class="{status_color}">{status_text}</td>
                    <td>{order.get('timestamp', 'N/A')[:16]}</td>
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)

application = app