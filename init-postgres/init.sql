CREATE TABLE sales (
    id SERIAL PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    sale_amount DECIMAL(10,2) NOT NULL,
    sale_date DATE NOT NULL,
    customer_id INT NOT NULL
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50)
);

INSERT INTO products (name, category) VALUES
('iPhone 16', 'Electronics'),
('MacBook Pro', 'Electronics'),
('Coffee Mug', 'Home');

INSERT INTO sales (product_name, sale_amount, sale_date, customer_id) VALUES
('iPhone 16', 999.99, '2025-11-15', 101),
('MacBook Pro', 2499.00, '2025-11-18', 102),
('Coffee Mug', 19.99, '2025-11-20', 103);
