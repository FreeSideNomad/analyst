import type {
  DatasetSummary,
  DatasetDetail,
  ColumnProfile,
  CatalogEntry,
  DatabaseConnection,
} from '../../api/types';

// ─── Dataset Summaries ──────────────────────────────────────────────────────

export const mockDatasets: DatasetSummary[] = [
  {
    id: 'ds-sales-001',
    name: 'sales',
    fileName: 'sales_2024.csv',
    rowCount: 143209,
    columnCount: 8,
    sizeBytes: 52_400_000,
    ingestedAt: '2025-12-10T14:23:00Z',
    status: 'ready',
  },
  {
    id: 'ds-customers-002',
    name: 'customers',
    fileName: 'customers_master.csv',
    rowCount: 12488,
    columnCount: 6,
    sizeBytes: 3_800_000,
    ingestedAt: '2025-12-11T09:05:00Z',
    status: 'ready',
  },
  {
    id: 'ds-products-003',
    name: 'products',
    fileName: 'product_catalog.csv',
    rowCount: 1847,
    columnCount: 5,
    sizeBytes: 420_000,
    ingestedAt: '2025-12-12T16:30:00Z',
    status: 'ready',
  },
];

// ─── Column profiles for each dataset ───────────────────────────────────────

const salesColumns: ColumnProfile[] = [
  {
    name: 'order_id',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 143209,
    sample: ['ORD-100001', 'ORD-100002', 'ORD-100003'],
  },
  {
    name: 'order_date',
    dtype: 'DATE',
    nullCount: 12,
    nullPercent: 0.01,
    uniqueCount: 365,
    sample: ['2024-01-15', '2024-03-22', '2024-07-04'],
  },
  {
    name: 'customer_id',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 11204,
    sample: ['CUST-2001', 'CUST-5832', 'CUST-9104'],
  },
  {
    name: 'product_id',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 1847,
    sample: ['PROD-101', 'PROD-422', 'PROD-780'],
  },
  {
    name: 'quantity',
    dtype: 'INTEGER',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 48,
    sample: [1, 3, 12],
    min: 1,
    max: 50,
    mean: 4.2,
    median: 3,
    stddev: 3.8,
    q25: 1,
    q75: 5,
  },
  {
    name: 'unit_price',
    dtype: 'DOUBLE',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 320,
    sample: [9.99, 49.95, 249.0],
    min: 0.99,
    max: 1299.99,
    mean: 87.42,
    median: 49.95,
    stddev: 112.3,
    q25: 19.99,
    q75: 99.99,
  },
  {
    name: 'billing_region',
    dtype: 'VARCHAR',
    nullCount: 237,
    nullPercent: 0.17,
    uniqueCount: 4,
    sample: ['North', 'South', 'East'],
  },
  {
    name: 'channel',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 3,
    sample: ['online', 'retail', 'wholesale'],
  },
];

const customerColumns: ColumnProfile[] = [
  {
    name: 'customer_id',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 12488,
    sample: ['CUST-2001', 'CUST-5832', 'CUST-9104'],
  },
  {
    name: 'customer_name',
    dtype: 'VARCHAR',
    nullCount: 3,
    nullPercent: 0.02,
    uniqueCount: 12420,
    sample: ['Acme Corp', 'Globex Inc', 'Initech LLC'],
  },
  {
    name: 'email',
    dtype: 'VARCHAR',
    nullCount: 45,
    nullPercent: 0.36,
    uniqueCount: 12340,
    sample: ['john@acme.co', 'jane@globex.com', null],
  },
  {
    name: 'region',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 4,
    sample: ['North', 'South', 'East'],
  },
  {
    name: 'signup_date',
    dtype: 'DATE',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 1820,
    sample: ['2019-06-01', '2021-11-15', '2023-02-28'],
  },
  {
    name: 'lifetime_value',
    dtype: 'DOUBLE',
    nullCount: 128,
    nullPercent: 1.02,
    uniqueCount: 9870,
    sample: [1250.0, 89.5, 34200.0],
    min: 0,
    max: 182_450.0,
    mean: 8_920.5,
    median: 4_350.0,
    stddev: 12_400.0,
    q25: 980.0,
    q75: 11_200.0,
  },
];

const productColumns: ColumnProfile[] = [
  {
    name: 'product_id',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 1847,
    sample: ['PROD-101', 'PROD-422', 'PROD-780'],
  },
  {
    name: 'product_name',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 1847,
    sample: ['Wireless Mouse', 'USB-C Hub', '4K Monitor'],
  },
  {
    name: 'category',
    dtype: 'VARCHAR',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 12,
    sample: ['Electronics', 'Accessories', 'Furniture'],
  },
  {
    name: 'list_price',
    dtype: 'DOUBLE',
    nullCount: 0,
    nullPercent: 0,
    uniqueCount: 310,
    sample: [29.99, 59.95, 499.0],
    min: 0.99,
    max: 2499.99,
    mean: 124.6,
    median: 59.95,
    stddev: 185.2,
    q25: 19.99,
    q75: 149.99,
  },
  {
    name: 'weight_kg',
    dtype: 'DOUBLE',
    nullCount: 72,
    nullPercent: 3.9,
    uniqueCount: 420,
    sample: [0.12, 1.5, 8.2],
    min: 0.01,
    max: 45.0,
    mean: 3.8,
    median: 1.2,
    stddev: 5.6,
    q25: 0.3,
    q75: 4.5,
  },
];

// ─── Dataset Details (keyed by ID) ─────────────────────────────────────────

export const mockDatasetDetails: Record<string, DatasetDetail> = {
  'ds-sales-001': {
    ...mockDatasets[0],
    columns: salesColumns,
  },
  'ds-customers-002': {
    ...mockDatasets[1],
    columns: customerColumns,
  },
  'ds-products-003': {
    ...mockDatasets[2],
    columns: productColumns,
  },
};

// ─── Catalog Entries ────────────────────────────────────────────────────────

export const mockCatalogEntries: CatalogEntry[] = [
  {
    datasetId: 'ds-sales-001',
    datasetName: 'sales',
    tableDescription:
      'Transactional sales orders for fiscal year 2024, covering online, retail, and wholesale channels.',
    columns: [
      { name: 'order_id', dtype: 'VARCHAR', description: 'Unique order identifier', role: 'key' },
      { name: 'order_date', dtype: 'DATE', description: 'Date the order was placed', role: 'timestamp' },
      { name: 'customer_id', dtype: 'VARCHAR', description: 'Foreign key to the customers table', role: 'key' },
      { name: 'product_id', dtype: 'VARCHAR', description: 'Foreign key to the products table', role: 'key' },
      { name: 'quantity', dtype: 'INTEGER', description: 'Number of units ordered', role: 'measure' },
      { name: 'unit_price', dtype: 'DOUBLE', description: 'Price per unit at time of sale', role: 'measure' },
      { name: 'billing_region', dtype: 'VARCHAR', description: 'Billing address region', role: 'dimension' },
      { name: 'channel', dtype: 'VARCHAR', description: 'Sales channel (online, retail, wholesale)', role: 'dimension' },
    ],
    relationships: [
      {
        fromDataset: 'ds-sales-001',
        fromColumn: 'customer_id',
        toDataset: 'ds-customers-002',
        toColumn: 'customer_id',
        confidence: 0.97,
      },
    ],
  },
  {
    datasetId: 'ds-customers-002',
    datasetName: 'customers',
    tableDescription:
      'Master customer records including contact information, region, and calculated lifetime value.',
    columns: [
      { name: 'customer_id', dtype: 'VARCHAR', description: 'Unique customer identifier', role: 'key' },
      { name: 'customer_name', dtype: 'VARCHAR', description: 'Full company or individual name', role: 'text' },
      { name: 'email', dtype: 'VARCHAR', description: 'Primary contact email', role: 'text' },
      { name: 'region', dtype: 'VARCHAR', description: 'Geographic region of the customer', role: 'dimension' },
      { name: 'signup_date', dtype: 'DATE', description: 'Date the customer account was created', role: 'timestamp' },
      { name: 'lifetime_value', dtype: 'DOUBLE', description: 'Total revenue attributed to the customer', role: 'measure' },
    ],
    relationships: [],
  },
  {
    datasetId: 'ds-products-003',
    datasetName: 'products',
    tableDescription:
      'Product catalog with pricing and physical attributes.',
    columns: [
      { name: 'product_id', dtype: 'VARCHAR', description: 'Unique product SKU identifier', role: 'key' },
      { name: 'product_name', dtype: 'VARCHAR', description: 'Display name of the product', role: 'text' },
      { name: 'category', dtype: 'VARCHAR', description: 'Product category', role: 'dimension' },
      { name: 'list_price', dtype: 'DOUBLE', description: 'Current list price in USD', role: 'measure' },
      { name: 'weight_kg', dtype: 'DOUBLE', description: 'Shipping weight in kilograms', role: 'measure' },
    ],
    relationships: [],
  },
];

// ─── Database Connections ───────────────────────────────────────────────────

export const mockDatabases: DatabaseConnection[] = [
  {
    id: 'db-pg-001',
    name: 'Production Warehouse',
    type: 'postgres',
    host: 'warehouse.internal.acme.co',
    port: 5432,
    database: 'analytics',
    status: 'connected',
    lastSyncAt: '2025-12-15T08:00:00Z',
  },
];
