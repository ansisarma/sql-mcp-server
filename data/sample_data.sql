CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    city VARCHAR(100),
    email VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    order_date DATE,
    total DECIMAL(10, 2)
);

INSERT INTO customers (name, city, email) VALUES
    ('Alice Schmidt', 'Berlin', 'alice@example.com'),
    ('Bob Müller', 'Munich', 'bob@example.com'),
    ('Carol Weber', 'Berlin', 'carol@example.com'),
    ('David Fischer', 'Hamburg', 'david@example.com'),
    ('Eve Bauer', 'Berlin', 'eve@example.com');

INSERT INTO orders (customer_id, order_date, total) VALUES
    (1, '2026-01-15', 150.00),
    (1, '2026-02-20', 200.00),
    (2, '2026-01-10', 75.50),
    (3, '2026-03-05', 300.00),
    (5, '2026-03-10', 125.75);
