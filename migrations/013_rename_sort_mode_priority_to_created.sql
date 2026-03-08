-- Rename sort_mode 'priority' -> 'created' in categories table
UPDATE categories SET sort_mode = 'created' WHERE sort_mode = 'priority';
