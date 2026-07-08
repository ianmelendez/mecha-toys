from flask import Flask, render_template, request, send_from_directory, jsonify, session, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime
import secrets
import os
import requests

# ===== IMPORTAR SENDGRID CORRECTAMENTE =====
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__, 
            template_folder='templates',
            static_folder='.')
app.secret_key = secrets.token_hex(16)

# ===== EMAIL CONFIGURATION =====
YOUR_EMAIL = "mecchachameleonstore@gmail.com"

# ===== SENDGRID CONFIGURATION =====
# Lee la API Key de las variables de entorno (NUNCA la pongas en el código)
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

# ===== PAYPAL STANDARD CONFIGURATION =====
PAYPAL_EMAIL = "mecchachameleonstore@gmail.com"
PAYPAL_SANDBOX = False
PAYPAL_URL = "https://www.paypal.com/cgi-bin/webscr"

# ===== PRODUCTS =====
PRODUCTS = {
    "8poses": {
        "id": "8poses",
        "name": "8 Poses Toy Set",
        "price": 0.01,
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

# ============================================================
# ===== FUNCIÓN DE EMAIL CON SENDGRID =====
# ============================================================

def send_email_sendgrid(to_email, subject, body):
    """Envía email usando SendGrid"""
    if not SENDGRID_API_KEY:
        print("❌ ERROR: SENDGRID_API_KEY no configurada")
        return False
        
    try:
        print(f"📤 Enviando email a {to_email} via SendGrid...")
        
        # Crear el mensaje
        message = Mail(
            from_email=YOUR_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=body.replace('\n', '<br>')
        )
        
        # === DESACTIVAR SANDBOX (FORMA CORRECTA) ===
        # En lugar de set_sandbox_mode, usamos el objeto sandbox_mode
        from sendgrid.helpers.mail import SandBoxMode
        message.sandbox_mode = SandBoxMode(False)  # ← AÑADE ESTA LÍNEA
        
        # Enviar
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            print(f"✅ Email enviado a {to_email}")
            print(f"📊 Status: {response.status_code}")
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def send_order_email(customer_name, customer_email, customer_address, product, phone=None, order_id=None, txn_id=None):
    """Envía emails al vendedor y al cliente usando SendGrid"""
    print(f"📧 ENVIANDO EMAILS PARA PEDIDO: {order_id}")
    
    # === EMAIL AL VENDEDOR ===
    you_subject = f"🛒 NUEVO PEDIDO - {product['name']}"
    you_body = f"""
    <h2>🎉 NUEVO PEDIDO RECIBIDO!</h2>
    
    <p><strong>ID del Pedido:</strong> {order_id or 'N/A'}</p>
    <p><strong>Producto:</strong> {product['name']}</p>
    <p><strong>Precio:</strong> €{product['price']}</p>
    <p><strong>ID de Transacción:</strong> {txn_id or 'N/A'}</p>
    
    <h3>DATOS DEL CLIENTE:</h3>
    <p><strong>Nombre:</strong> {customer_name}</p>
    <p><strong>Email:</strong> {customer_email}</p>
    <p><strong>Teléfono:</strong> {phone or 'No proporcionado'}</p>
    <p><strong>Dirección:</strong> {customer_address}</p>
    
    <p><strong>Fecha:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h3>⚡ ACCIÓN REQUERIDA:</h3>
    <ol>
        <li>PayPal te ha notificado el pago</li>
        <li>Ve al enlace de AliExpress</li>
        <li>Añade al carrito y completa la compra</li>
        <li>Envía al cliente</li>
    </ol>
    
    <p><strong>ENLACE DE ALIEXPRESS:</strong><br>
    <a href="{product['aliexpress_link']}">{product['aliexpress_link']}</a></p>
    """
    
    send_email_sendgrid(YOUR_EMAIL, you_subject, you_body)
    
    # === EMAIL AL CLIENTE ===
    customer_subject = f"✅ Confirmación de Pedido - Mecha Toys"
    customer_body = f"""
    <h2>✅ ¡Gracias por tu pedido, {customer_name}!</h2>
    
    <p>Hemos recibido tu pago correctamente.</p>
    
    <h3>Detalles del Pedido:</h3>
    <p><strong>ID del Pedido:</strong> {order_id or 'N/A'}</p>
    <p><strong>Producto:</strong> {product['name']}</p>
    <p><strong>Precio:</strong> €{product['price']}</p>
    <p><strong>Método de Pago:</strong> PayPal</p>
    
    <h3>Dirección de Envío:</h3>
    <p>{customer_address}</p>
    
    <h3>Próximos Pasos:</h3>
    <ol>
        <li>Procesaremos tu pedido en 24 horas</li>
        <li>Te enviaremos un número de seguimiento por email</li>
        <li>El envío tarda 7-15 días hábiles</li>
    </ol>
    
    <p>¿Preguntas? Responde a este email.</p>
    
    <p>¡Gracias por elegir Mecha Toys! 🦎</p>
    """
    
    send_email_sendgrid(customer_email, customer_subject, customer_body)

# ============================================================
# ===== FUNCIÓN PARA PROCESAR PEDIDOS =====
# ============================================================

def process_order(customer_data, product, txn_id=None):
    """Procesa un pedido y guarda en orders.json"""
    print(f"📦 PROCESANDO PEDIDO: {customer_data.get('name', 'Unknown')}")
    
    if not product:
        print("❌ Producto no encontrado")
        return None
    
    order_id = f"MT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    order_data = {
        'order_id': order_id,
        'product': product['name'],
        'product_id': product['id'],
        'customer_name': customer_data.get('name', 'Unknown'),
        'customer_email': customer_data.get('email', 'Unknown'),
        'customer_phone': customer_data.get('phone', ''),
        'customer_address': customer_data.get('address', 'No address provided'),
        'aliexpress_link': product['aliexpress_link'],
        'amount': product['price'],
        'timestamp': datetime.now().isoformat(),
        'status': 'paid',
        'payment_method': 'paypal',
        'paypal_txn_id': txn_id or 'N/A'
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
    print(f"✅ Pedido guardado: {order_id}")
    
    # ENVIAR EMAILS
    send_order_email(
        customer_data.get('name', 'Unknown'),
        customer_data.get('email', 'Unknown'),
        customer_data.get('address', 'No address provided'),
        product,
        customer_data.get('phone', ''),
        order_id,
        txn_id
    )
    
    return order_data

# ============================================================
# ===== PAYPAL IPN =====
# ============================================================

@app.route('/paypal-ipn', methods=['POST'])
def paypal_ipn():
    print("=== 📨 IPN RECIBIDO ===")
    
    try:
        data = request.form.to_dict()
        data['cmd'] = '_notify-validate'
        response = requests.post(PAYPAL_URL, data=data)
        print(f"IPN verification: {response.text}")
        
        if response.text == 'VERIFIED':
            print("✅ IPN verificado")
            
            txn_id = request.form.get('txn_id')
            payment_status = request.form.get('payment_status')
            custom = request.form.get('custom')
            
            if payment_status == 'Completed':
                customer_data = json.loads(custom) if custom else {}
                product_id = customer_data.get('product_id')
                product = PRODUCTS.get(product_id)
                
                if product:
                    order_data = process_order(customer_data, product, txn_id)
                    if order_data:
                        print(f"✅ IPN: Pedido {order_data['order_id']} procesado")
                        return 'OK', 200
            else:
                print(f"⚠️ Status: {payment_status}")
        else:
            print(f"❌ IPN no verificado")
            
    except Exception as e:
        print(f"❌ IPN Error: {e}")
    
    return 'OK', 200

# ============================================================
# ===== ROUTES =====
# ============================================================

@app.route('/')
def home():
    return render_template('index.html', products=PRODUCTS)

@app.route('/checkout/<product_id>', methods=['GET'])
def checkout(product_id):
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    return render_template('checkout.html', product=product)

@app.route('/checkout/<product_id>', methods=['POST'])
def process_checkout(product_id):
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone', '')
    address = request.form.get('address')
    
    if not all([name, email, address]):
        return "Missing required fields", 400
    
    session['customer_data'] = {
        'name': name,
        'email': email,
        'phone': phone,
        'address': address,
        'product_id': product_id
    }
    
    return redirect(url_for('paypal_redirect', product_id=product_id))

@app.route('/paypal-redirect/<product_id>')
def paypal_redirect(product_id):
    product = PRODUCTS.get(product_id)
    if not product:
        return "Product not found", 404
    
    customer_data = session.get('customer_data', {})
    
    custom_data = json.dumps({
        'product_id': product_id,
        'name': customer_data.get('name'),
        'email': customer_data.get('email'),
        'address': customer_data.get('address'),
        'phone': customer_data.get('phone')
    })
    
    notify_url = "https://mecha-toys.onrender.com/paypal-ipn"
    return_url = "https://mecha-toys.onrender.com/payment-success"
    cancel_url = "https://mecha-toys.onrender.com/payment-cancel"
    
    paypal_form = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Redirecting to PayPal...</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 50px 40px;
                border-radius: 24px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.08);
                text-align: center;
                max-width: 450px;
                width: 100%;
            }}
            .spinner {{
                width: 50px;
                height: 50px;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #0070ba;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 20px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            h2 {{ color: #1a1a2e; font-size: 1.5rem; margin-bottom: 8px; }}
            p {{ color: #636e72; margin-bottom: 20px; line-height: 1.6; }}
            .btn {{
                display: inline-block;
                padding: 14px 40px;
                background: #0070ba;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 1.1rem;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 4px 20px rgba(0, 112, 186, 0.3);
                text-decoration: none;
            }}
            .btn:hover {{
                background: #003087;
                transform: translateY(-3px);
                box-shadow: 0 8px 30px rgba(0, 112, 186, 0.4);
            }}
            .info {{ margin-top: 20px; font-size: 0.85rem; color: #b2bec3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="spinner"></div>
            <h2>🔄 Redirecting to PayPal...</h2>
            <p>Please wait while we redirect you to PayPal to complete your payment.</p>
            
            <form action="{PAYPAL_URL}" method="post" id="paypal-form">
                <input type="hidden" name="cmd" value="_xclick">
                <input type="hidden" name="business" value="{PAYPAL_EMAIL}">
                <input type="hidden" name="lc" value="EN">
                <input type="hidden" name="item_name" value="{product['name']}">
                <input type="hidden" name="amount" value="{product['price']}">
                <input type="hidden" name="currency_code" value="EUR">
                <input type="hidden" name="button_subtype" value="services">
                <input type="hidden" name="no_note" value="1">
                <input type="hidden" name="tax_rate" value="0.00">
                <input type="hidden" name="shipping" value="0.00">
                <input type="hidden" name="return" value="{return_url}">
                <input type="hidden" name="cancel_return" value="{cancel_url}">
                <input type="hidden" name="rm" value="2">
                <input type="hidden" name="notify_url" value="{notify_url}">
                <input type="hidden" name="custom" value='{custom_data}'>
            </form>
            
            <button onclick="document.getElementById('paypal-form').submit();" class="btn">💳 Go to PayPal</button>
            <p class="info">If you are not redirected automatically, click the button above.</p>
            <a href="/" style="display:block; margin-top: 15px; color: #636e72; text-decoration: none; font-size: 0.9rem;">← Back to Store</a>
        </div>
        
        <script>
            setTimeout(function() {{
                document.getElementById('paypal-form').submit();
            }}, 1500);
        </script>
    </body>
    </html>
    """
    return paypal_form

@app.route('/payment-success', methods=['GET', 'POST'])
def payment_success():
    print("=== ✅ PAYMENT SUCCESS CALLED ===")
    
    customer_data = session.get('customer_data', {})
    product_id = customer_data.get('product_id')
    product = PRODUCTS.get(product_id) if product_id else None
    
    if product and customer_data.get('name'):
        txn_id = request.args.get('txn_id') or request.form.get('txn_id')
        order_data = process_order(customer_data, product, txn_id)
        if order_data:
            session.pop('customer_data', None)
    
    return render_template('success.html')

@app.route('/payment-cancel')
def payment_cancel():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Payment Cancelled - Mecha Toys</title>
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
            <h2>⚠️ Payment Cancelled</h2>
            <p>Your payment was cancelled. No charges were made.</p>
            <a href="/" class="btn">← Back to Store</a>
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
            <title>📦 Orders - Mecha Toys</title>
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
                <h1>📦 All Orders</h1>
                <p class="total">Total: <strong>""" + str(len(orders)) + """</strong></p>
        """
        
        if orders:
            html += """
            <table>
                <tr>
                    <th>Order ID</th>
                    <th>Product</th>
                    <th>Customer</th>
                    <th>Total</th>
                    <th>Status</th>
                    <th>Date</th>
                </tr>
            """
            
            for order in reversed(orders):
                status_color = "status-paid" if order.get('status') == 'paid' else ""
                status_text = "✅ PAID" if order.get('status') == 'paid' else "⏳ PENDING"
                html += f"""
                <tr>
                    <td><strong>{order.get('order_id', 'N/A')}</strong></td>
                    <td>{order.get('product', 'N/A')}</td>
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
                <h2>📭 No orders yet</h2>
                <p>Orders will appear here when customers make purchases.</p>
            </div>
            """
        
        html += """
            <a href="/" class="back-link">← Back to Store</a>
            </div>
        </body>
        </html>
        """
        return html
        
    except FileNotFoundError:
        return """
        <div style="text-align:center;padding:60px;">
            <h2>📭 No orders yet</h2>
            <a href="/" style="display:inline-block;margin-top:20px;padding:12px 30px;background:#0070ba;color:white;text-decoration:none;border-radius:10px;">← Back to Store</a>
        </div>
        """

if __name__ == '__main__':
    app.run(debug=True, port=5000)

application = app