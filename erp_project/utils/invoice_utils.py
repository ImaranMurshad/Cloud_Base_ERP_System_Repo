def calculate_total(items):
    total = 0
    for item in items:
        total += item["price"] * item["quantity"]
    return total


def calculate_subtotal(price, quantity):
    return price * quantity
