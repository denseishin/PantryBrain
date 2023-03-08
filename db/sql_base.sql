create table product(
	EAN INTEGER NOT NULL,
	product_name varchar,
	producer varchar,
	net_weight decimal(6,2),
	max_weight decimal(6,2),
	last_update datetime,
	source INTEGER,
	PRIMARY KEY (EAN)
	);

create table inventory(
	item_id INTEGER PRIMARY KEY AUTOINCREMENT,
	EAN INTEGER references item(EAN),
	current_weight decimal(6,2) NOT NULL,
	expiry_date date,
	batch varchar,
	pos_x INTEGER,
	pos_y INTEGER,
	shelf INTEGER,
	comment varchar,
	add_time datetime,
	out_time datetime,
	in_time datetime
	);

create table usage_log(
	item_id INTEGER references inventory(item_id),
	action_time datetime NOT NULL,
	action_type INTEGER,
	weight decimal(6,2),
	PRIMARY KEY (item_id, action_time)
	);

create table inv_photos(
	photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
	item_id INTEGER references inventory(item_id),
	photo blob NOT NULL,
	taken_at datetime
	);

create table recalls(
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	reason varchar,
	issued_at date,
	info_url varchar,
	source integer
	);

create table recalled_batches(
	recall_id INTEGER NOT NULL REFERENCES recalls(id),
	batch varchar,
	PRIMARY KEY (recall_id, batch)
	);

create table recalled_expiry_dates(
	recall_id INTEGER NOT NULL REFERENCES recalls(id),
	expiry_date date,
	PRIMARY KEY (recall_id, expiry_date)
	);

create table recalled_upcs(
	recall_id INTEGER NOT NULL REFERENCES recalls(id),
	UPC integer references product(EAN),
	PRIMARY KEY (recall_id, UPC)
	);