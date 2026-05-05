// Base URL: les peticions van a /api i Nginx les redirigeix a l'api-gateway
const API = '/api';

let currentToken = null;
let currentUser = null;

// ============== USUARIS ==============
async function registerUser() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    if (!username || !password) {
        showResult('user-result', 'Cal omplir usuari i contrasenya', 'error');
        return;
    }
    try {
        const res = await fetch(`${API}/users/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            showResult('user-result', `✅ ${data.message}: ${data.username}`, 'success');
        } else {
            showResult('user-result', `❌ ${data.error}`, 'error');
        }
    } catch (e) {
        showResult('user-result', `❌ Error de xarxa: ${e.message}`, 'error');
    }
}

async function loginUser() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    try {
        const res = await fetch(`${API}/users/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            currentToken = data.token;
            currentUser = username;
            document.getElementById('user-status').textContent = `✓ Sessió: ${username}`;
            showResult('user-result',
                `✅ Login correcte\nToken JWT (primers 40 caràcters):\n${data.token.substring(0, 40)}...`,
                'success');
        } else {
            showResult('user-result', `❌ ${data.error}`, 'error');
        }
    } catch (e) {
        showResult('user-result', `❌ Error de xarxa: ${e.message}`, 'error');
    }
}

// ============== PRODUCTES (FLUX 1) ==============
async function loadProducts() {
    try {
        const res = await fetch(`${API}/products`);
        const data = await res.json();

        // Mostrem si la dada ve de DB o de cache (Redis)
        const badge = document.getElementById('products-source');
        if (data.source === 'cache') {
            badge.className = 'badge cache';
            badge.textContent = '⚡ Origen: Redis (cache)';
        } else {
            badge.className = 'badge db';
            badge.textContent = '🗄️ Origen: db-products (MySQL)';
        }

        // Pintem la llista
        const list = document.getElementById('products-list');
        list.innerHTML = '';
        const select = document.getElementById('product-select');
        select.innerHTML = '<option value="">-- Selecciona un producte --</option>';

        data.data.forEach(p => {
            const item = document.createElement('div');
            item.className = 'product-item';
            item.innerHTML = `
                <div>
                    <strong>${p.name}</strong>
                    <span style="color:#7f8c8d;"> · Stock: ${p.stock}</span>
                </div>
                <span class="price">${p.price.toFixed(2)} €</span>
            `;
            list.appendChild(item);

            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = `${p.name} (stock: ${p.stock})`;
            select.appendChild(opt);
        });
    } catch (e) {
        document.getElementById('products-list').innerHTML =
            `<p style="color:#c0392b;">Error: ${e.message}</p>`;
    }
}

// ============== COMANDES (FLUX 2) ==============
async function createOrder() {
    const productId = document.getElementById('product-select').value;
    const quantity = parseInt(document.getElementById('quantity').value);

    if (!productId) {
        showResult('order-result', 'Selecciona un producte primer', 'error');
        return;
    }

    try {
        const res = await fetch(`${API}/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: parseInt(productId), quantity })
        });
        const data = await res.json();

        if (res.ok) {
            showResult('order-result',
                `✅ ${data.message}\n` +
                `ID comanda: ${data.order.order_id}\n` +
                `Producte: ${data.order.product_name}\n` +
                `Quantitat: ${data.order.quantity}\n\n` +
                `📨 Missatge publicat a RabbitMQ\n` +
                `📝 Mira els logs: docker compose logs notification-service`,
                'success');
            // Refresquem productes (l'stock ha canviat) i historial
            loadProducts();
            loadOrders();
        } else {
            showResult('order-result', `❌ ${data.error}`, 'error');
        }
    } catch (e) {
        showResult('order-result', `❌ Error: ${e.message}`, 'error');
    }
}

// ============== HISTORIAL ==============
async function loadOrders() {
    try {
        const res = await fetch(`${API}/orders`);
        const data = await res.json();
        const list = document.getElementById('orders-list');
        list.innerHTML = '';

        if (data.length === 0) {
            list.innerHTML = '<p class="hint">Encara no hi ha comandes.</p>';
            return;
        }

        data.forEach(o => {
            const item = document.createElement('div');
            item.className = 'order-item';
            item.innerHTML = `
                <div>
                    <strong>Comanda #${o.id}</strong>
                    <span style="color:#7f8c8d;"> · Producte ID ${o.product_id} · Qty: ${o.quantity}</span>
                </div>
                <span style="font-size:0.85rem; color:#7f8c8d;">${o.created_at}</span>
            `;
            list.appendChild(item);
        });
    } catch (e) {
        document.getElementById('orders-list').innerHTML =
            `<p style="color:#c0392b;">Error: ${e.message}</p>`;
    }
}

// ============== UTILS ==============
function showResult(elementId, message, type) {
    const el = document.getElementById(elementId);
    el.textContent = message;
    el.className = `result ${type}`;
}

// En carregar la pàgina, carreguem els productes automàticament
window.addEventListener('DOMContentLoaded', () => {
    loadProducts();
    loadOrders();
});