import type {
  ClarificationResult,
  AnswerResult,
  ChatMessage,
} from '../../api/types';

// ─── Clarification Result ───────────────────────────────────────────────────

export const mockClarificationResult: ClarificationResult = {
  type: 'clarification',
  queryId: 'qry-clarify-001',
  question: 'There are two region columns available. Which one would you like to use?',
  options: [
    {
      label: 'billing_region (sales)',
      value: 'billing_region',
      description: 'Region from the sales billing address — 237 nulls, 4 distinct values.',
    },
    {
      label: 'region (customers)',
      value: 'customer_region',
      description: 'Geographic region of the customer record — no nulls, 4 distinct values.',
    },
  ],
};

// ─── Answer Result — Revenue by Billing Region ─────────────────────────────

export const mockAnswerResult: AnswerResult = {
  type: 'answer',
  queryId: 'qry-answer-001',
  summary:
    'Total revenue by billing region for 2024. The East region generated the highest revenue at $4.2M, followed by North at $3.8M.',
  chartType: 'bar',
  chartData: [
    { label: 'East', value: 4_218_340 },
    { label: 'North', value: 3_812_150 },
    { label: 'South', value: 2_945_600 },
    { label: 'West', value: 1_673_900 },
  ],
  trustTrail: {
    assumptions: [
      'Revenue is calculated as quantity × unit_price.',
      'Rows with NULL billing_region (237 of 143 209) are excluded.',
      'All dates are within fiscal year 2024.',
    ],
    lineage: [
      'Source table: sales (ds-sales-001)',
      'Columns used: billing_region, quantity, unit_price',
      'Filter: order_date BETWEEN \'2024-01-01\' AND \'2024-12-31\'',
    ],
    sql: `SELECT
  billing_region,
  SUM(quantity * unit_price) AS total_revenue
FROM sales
WHERE order_date BETWEEN '2024-01-01' AND '2024-12-31'
  AND billing_region IS NOT NULL
GROUP BY billing_region
ORDER BY total_revenue DESC;`,
  },
};

// ─── Multi-Table Result — Top 5 Customers by Revenue ───────────────────────

export const mockMultiTableResult: AnswerResult = {
  type: 'answer',
  queryId: 'qry-multi-001',
  summary:
    'Top 5 customers by total revenue in 2024. Acme Corp leads with $482K, followed by Globex Inc at $391K.',
  chartType: 'bar',
  chartData: [
    { label: 'Acme Corp', value: 482_100 },
    { label: 'Globex Inc', value: 391_400 },
    { label: 'Initech LLC', value: 287_600 },
    { label: 'Umbrella Co', value: 245_900 },
    { label: 'Stark Industries', value: 198_300 },
  ],
  trustTrail: {
    assumptions: [
      'Revenue is calculated as quantity × unit_price from the sales table.',
      'Customer names are resolved via an inner join on customer_id.',
      'Only orders from fiscal year 2024 are included.',
    ],
    lineage: [
      'Source tables: sales (ds-sales-001), customers (ds-customers-002)',
      'Join: sales.customer_id = customers.customer_id',
      'Columns used: customer_name, quantity, unit_price, order_date',
    ],
    sql: `SELECT
  c.customer_name,
  SUM(s.quantity * s.unit_price) AS total_revenue
FROM sales s
INNER JOIN customers c
  ON s.customer_id = c.customer_id
WHERE s.order_date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY c.customer_name
ORDER BY total_revenue DESC
LIMIT 5;`,
  },
};

// ─── Initial Conversation ───────────────────────────────────────────────────

export const mockInitialConversation: ChatMessage[] = [];
