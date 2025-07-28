// src/webapp/static/js/app.js
const tg = window.Telegram.WebApp;

const app = Vue.createApp({
    data() {
        return {
            isLoading: true,
            currentView: 'catalog', // 'catalog', 'product', 'cart'
            products: [],
            currentProduct: null,
            selectedVariant: null,
            cart: [], // { variant_id, product_name, photo_url, size, price, quantity }
            filters: {
                category: '',
                brand: ''
            },
            searchQuery: '',
            tg: window.Telegram.WebApp,
        };
    },
    computed: {
        uniqueBrands() {
            const brands = new Set(this.products.map(p => p.brand));
            return Array.from(brands).sort();
        },
        filteredProducts() {
            let filtered = this.products;

            if (this.filters.category) {
                filtered = filtered.filter(p => p.category === this.filters.category);
            }
            if (this.filters.brand) {
                filtered = filtered.filter(p => p.brand === this.filters.brand);
            }
            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(p => p.name.toLowerCase().includes(query) || p.brand.toLowerCase().includes(query));
            }

            return filtered;
        },
        cartCount() {
            return this.cart.reduce((total, item) => total + item.quantity, 0);
        },
        cartTotal() {
            return this.cart.reduce((total, item) => total + item.price * item.quantity, 0);
        },
        isProductInCart() {
            if (!this.selectedVariant) return false;
            return this.cart.some(item => item.variant_id === this.selectedVariant.id);
        }
    },
    methods: {
        async fetchProducts() {
            this.isLoading = true;
            try {
                const response = await fetch('/api/products');
                if (!response.ok) throw new Error('Network response was not ok');
                this.products = await response.json();
            } catch (error) {
                console.error("Failed to fetch products:", error);
                this.tg.showAlert('Не удалось загрузить товары.');
            } finally {
                this.isLoading = false;
            }
        },
        async showProduct(productId) {
            this.isLoading = true;
            this.currentProduct = null;
            this.selectedVariant = null;
            try {
                const response = await fetch(`/api/product/${productId}`);
                if (!response.ok) throw new Error('Product not found');
                this.currentProduct = await response.json();
                this.showView('product');
            } catch (error) {
                console.error("Failed to fetch product details:", error);
                this.tg.showAlert('Не удалось загрузить информацию о товаре.');
            } finally {
                this.isLoading = false;
            }
        },
        showView(viewName) {
            this.currentView = viewName;
            window.scrollTo(0, 0); // Прокручиваем наверх при смене вида
            this.updateMainButton();
        },
        selectVariant(variant) {
            this.selectedVariant = variant;
        },
        addToCart() {
            if (!this.selectedVariant) return;
            const existingItem = this.cart.find(item => item.variant_id === this.selectedVariant.id);

            if (existingItem) {
                this.tg.showPopup({
                    title: 'Уведомление',
                    message: 'Этот товар уже в корзине. Вы можете изменить количество в корзине.',
                    buttons: [{ type: 'ok' }]
                });
                return;
            }

            this.cart.push({
                variant_id: this.selectedVariant.id,
                product_name: this.currentProduct.name,
                photo_url: this.currentProduct.photo_url,
                size: this.selectedVariant.size,
                price: this.selectedVariant.price,
                quantity: 1
            });

            this.saveCart();
            this.tg.HapticFeedback.notificationOccurred('success');
        },
        updateQuantity(variant_id, delta) {
            const item = this.cart.find(i => i.variant_id === variant_id);
            if (item) {
                item.quantity += delta;
                if (item.quantity <= 0) {
                    this.cart = this.cart.filter(i => i.variant_id !== variant_id);
                }
            }
            this.tg.HapticFeedback.impactOccurred('light');
            this.saveCart();
            this.updateMainButton();
        },
        placeOrder() {
            if (this.cart.length === 0) return;

            const orderData = {
                event: 'newOrder',
                data: {
                    items: this.cart,
                    total_amount: this.cartTotal,
                }
            };

            this.tg.sendData(JSON.stringify(orderData));
            // Очистка корзины после отправки
            this.cart = [];
            localStorage.removeItem('vibesCart');
        },
        saveCart() {
            localStorage.setItem('vibesCart', JSON.stringify(this.cart));
        },
        loadCart() {
            const savedCart = localStorage.getItem('vibesCart');
            if (savedCart) {
                this.cart = JSON.parse(savedCart);
            }
        },
        configureTelegramUi() {
            this.tg.expand();
            this.tg.BackButton.onClick(() => this.showView('catalog'));
            this.tg.onEvent('mainButtonClicked', this.placeOrder);
        },
        updateMainButton() {
             if (this.currentView === 'cart' && this.cartCount > 0) {
                this.tg.MainButton.setText(`Оформить заказ на ${this.cartTotal.toFixed(0)} ₽`);
                this.tg.MainButton.show();
            } else {
                this.tg.MainButton.hide();
            }

            if (this.currentView === 'catalog') {
                this.tg.BackButton.hide();
            } else {
                this.tg.BackButton.show();
            }
        }
    },
    watch: {
        cart: {
            handler() {
                this.updateMainButton();
            },
            deep: true,
        },
        currentView() {
             this.updateMainButton();
        }
    },
    mounted() {
        this.configureTelegramUi();
        this.loadCart();
        this.fetchProducts();
        this.updateMainButton();
    }
});

app.mount('#app');