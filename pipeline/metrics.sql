SELECT paid_date, currency, COUNT(*) AS payment_count,
       SUM(amount_cents) AS total_amount_cents
FROM payments
GROUP BY paid_date, currency
ORDER BY paid_date, currency;

