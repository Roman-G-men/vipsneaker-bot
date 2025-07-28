# src/database/queries.py
import json
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import User, Product, ProductVariant, Order


# --- User Queries ---
def get_or_create_user(db: Session, tg_user):
    user = db.query(User).filter(User.telegram_id == tg_user.id).first()
    if not user:
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# --- Product Queries ---
def get_active_products_with_variants(db: Session):
    products = db.query(Product).filter(Product.is_active == True).order_by(desc(Product.id)).all()
    result = []
    for p in products:
        variants_in_stock = [v for v in p.variants if v.stock > 0]
        min_price = min((v.price for v in variants_in_stock), default=None)

        # Не добавляем товар в каталог, если ни одного варианта нет в наличии
        if not variants_in_stock:
            continue

        result.append({
            'id': p.id, 'name': p.name, 'brand': p.brand,
            'category': p.category, 'photo_url': p.photo_url,
            'min_price': min_price, 'sizes': [v.size for v in variants_in_stock]
        })
    return result


def get_product_details(db: Session, product_id: int):
    return db.query(Product).filter(Product.id == product_id).first()


def get_paginated_products(db: Session, page: int, per_page: int = 5):
    offset = page * per_page
    products = db.query(Product).order_by(desc(Product.id)).offset(offset).limit(per_page).all()
    total = db.query(Product).count()
    return products, total


def create_product(db: Session, product_data: dict):
    new_product = Product(
        name=product_data['name'], brand=product_data['brand'], category=product_data['category'],
        description=product_data['description'], composition=product_data['composition'],
        photo_url=product_data['photo_url']
    )
    for var_data in product_data['variants']:
        variant = ProductVariant(
            size=var_data['size'], price=var_data['price'], stock=var_data['stock']
        )
        new_product.variants.append(variant)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


def delete_product(db: Session, product_id: int):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        db.delete(product)
        db.commit()
        return True
    return False


# --- Order Queries ---
def create_order(db: Session, user: User, order_data: dict):
    # Уменьшаем кол-во товара на складе
    for item in order_data['items']:
        variant_id = item.get('variant_id')
        quantity = item.get('quantity', 0)

        variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).first()
        if variant and variant.stock >= quantity:
            variant.stock -= quantity
        else:
            # Если товара не хватает, вызываем исключение, чтобы откатить транзакцию
            raise ValueError(f"Недостаточно товара на складе для варианта ID {variant_id}")

    new_order = Order(
        user_id=user.id,
        items_json=json.dumps(order_data['items']),
        total_amount=order_data['total_amount'],
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order


def get_user_orders(db: Session, user: User, limit: int = 5):
    return db.query(Order).filter(Order.user_id == user.id).order_by(desc(Order.created_at)).limit(limit).all()