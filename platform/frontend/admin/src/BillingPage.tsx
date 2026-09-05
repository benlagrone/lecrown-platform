import { useEffect, useState } from "react";

import {
  createInvoiceDraft,
  downloadGeneratedInvoice,
  downloadRenderedInvoice,
  getInvoiceDefaults,
} from "../../shared/api";
import type {
  AuthUser,
  InvoiceCompositionMode,
  InvoiceDefaults,
  InvoiceDraftResult,
  InvoiceLineItem,
  InvoiceRenderRequest,
  InvoiceSenderMailbox,
} from "../../shared/types";

type BillingLineItemForm = {
  id: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
};

type BillingFormState = {
  company_key: string;
  sender_mailbox: string;
  recipient_email: string;
  cc_email: string;
  bill_to_name: string;
  bill_to_phone: string;
  bill_to_address: string;
  issue_date: string;
  due_date: string;
  memo: string;
  pay_online_label: string;
  pay_online_url: string;
  invoice_number_override: string;
  composition_mode: InvoiceCompositionMode;
  currency: string;
  hourly_rate: string;
  week_1_ending: string;
  week_1_hours: string;
  week_2_ending: string;
  week_2_hours: string;
  custom_line_items: BillingLineItemForm[];
};

type BillingPreviewLine = {
  description: string;
  quantity: number | null;
  unit_price: number | null;
  amount: number;
  subtotal_included: boolean;
};

type BillingPreview = {
  lineItems: BillingPreviewLine[];
  subtotal: number;
  total: number;
  amountDue: number;
};

let billingLineItemCounter = 0;

function nextLineItemId(): string {
  billingLineItemCounter += 1;
  return `billing-line-item-${billingLineItemCounter}`;
}

function createLineItemRow(lineItem?: Partial<BillingLineItemForm>): BillingLineItemForm {
  return {
    id: nextLineItemId(),
    description: lineItem?.description ?? "",
    quantity: lineItem?.quantity ?? "",
    unit_price: lineItem?.unit_price ?? "",
    amount: lineItem?.amount ?? "",
  };
}

function lineItemToRow(item: InvoiceLineItem): BillingLineItemForm {
  return createLineItemRow({
    description: item.description ?? "",
    quantity: item.quantity == null ? "" : String(item.quantity),
    unit_price: item.unit_price == null ? "" : String(item.unit_price),
    amount: String(item.amount ?? 0),
  });
}

function buildFormFromDefaults(defaults: InvoiceDefaults["defaults"]): BillingFormState {
  return {
    company_key: defaults.company_key,
    sender_mailbox: defaults.sender_mailbox,
    recipient_email: defaults.recipient_email,
    cc_email: defaults.cc_email ?? "",
    bill_to_name: defaults.bill_to_name,
    bill_to_phone: defaults.bill_to_phone ?? "",
    bill_to_address: defaults.bill_to_address,
    issue_date: defaults.issue_date,
    due_date: defaults.due_date,
    memo: defaults.memo,
    pay_online_label: defaults.pay_online_label ?? "",
    pay_online_url: defaults.pay_online_url ?? "",
    invoice_number_override: "",
    composition_mode: defaults.default_composition_mode,
    currency: defaults.currency,
    hourly_rate: String(defaults.hourly_rate),
    week_1_ending: defaults.week_1_ending,
    week_1_hours: String(defaults.week_1_hours),
    week_2_ending: defaults.week_2_ending,
    week_2_hours: String(defaults.week_2_hours),
    custom_line_items:
      defaults.custom_line_items.length > 0
        ? defaults.custom_line_items.map(lineItemToRow)
        : [createLineItemRow()],
  };
}

function parseOptionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function roundCurrency(value: number): number {
  return Math.round(value * 100) / 100;
}

function isTaxLine(description: string): boolean {
  return /^\s*tax\b/i.test(description);
}

function isBlankCustomLineItem(lineItem: BillingLineItemForm): boolean {
  return (
    !lineItem.description.trim() &&
    !lineItem.quantity.trim() &&
    !lineItem.unit_price.trim() &&
    !lineItem.amount.trim()
  );
}

function calculateCustomLineAmount(lineItem: BillingLineItemForm): number | null {
  const quantity = parseOptionalNumber(lineItem.quantity);
  const unitPrice = parseOptionalNumber(lineItem.unit_price);
  if (quantity != null && unitPrice != null) {
    return roundCurrency(quantity * unitPrice);
  }
  const amount = parseOptionalNumber(lineItem.amount);
  return amount == null ? null : roundCurrency(amount);
}

function calculatePreview(form: BillingFormState): BillingPreview {
  if (form.composition_mode === "time_entry") {
    const hourlyRate = parseOptionalNumber(form.hourly_rate) ?? 0;
    const week1Hours = parseOptionalNumber(form.week_1_hours) ?? 0;
    const week2Hours = parseOptionalNumber(form.week_2_hours) ?? 0;
    const week1Amount = roundCurrency(hourlyRate * week1Hours);
    const week2Amount = roundCurrency(hourlyRate * week2Hours);
    const total = roundCurrency(week1Amount + week2Amount);
    return {
      lineItems: [
        {
          description: `Week ending ${formatShortDate(form.week_1_ending)} (hours)`,
          quantity: week1Hours,
          unit_price: hourlyRate,
          amount: week1Amount,
          subtotal_included: true,
        },
        {
          description: `Week ending ${formatShortDate(form.week_2_ending)} (hours)`,
          quantity: week2Hours,
          unit_price: hourlyRate,
          amount: week2Amount,
          subtotal_included: true,
        },
      ],
      subtotal: total,
      total,
      amountDue: total,
    };
  }

  let subtotal = 0;
  let total = 0;
  const lineItems: BillingPreviewLine[] = [];
  for (const lineItem of form.custom_line_items) {
    if (isBlankCustomLineItem(lineItem)) {
      continue;
    }
    const amount = calculateCustomLineAmount(lineItem) ?? 0;
    const quantity = parseOptionalNumber(lineItem.quantity);
    const unitPrice = parseOptionalNumber(lineItem.unit_price);
    const subtotalIncluded = !isTaxLine(lineItem.description);
    lineItems.push({
      description: lineItem.description.trim() || "Untitled line item",
      quantity,
      unit_price: unitPrice,
      amount,
      subtotal_included: subtotalIncluded,
    });
    total = roundCurrency(total + amount);
    if (subtotalIncluded) {
      subtotal = roundCurrency(subtotal + amount);
    }
  }

  return {
    lineItems,
    subtotal,
    total,
    amountDue: total,
  };
}

function formatCurrency(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

function formatShortDate(value: string): string {
  if (!value) {
    return "Pending date";
  }
  const [yearText, monthText, dayText] = value.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return value;
  }
  return `${month}/${day}/${year}`;
}

function formatLongDate(value: string): string {
  if (!value) {
    return "Pending date";
  }
  const [yearText, monthText, dayText] = value.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return value;
  }
  const date = new Date(year, month - 1, day);
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

function buildPayload(form: BillingFormState): InvoiceRenderRequest {
  if (form.composition_mode === "custom") {
    const customLineItems = form.custom_line_items
      .filter((lineItem) => !isBlankCustomLineItem(lineItem))
      .map((lineItem) => {
        const description = lineItem.description.trim();
        if (!description) {
          throw new Error("Each custom line item needs a description.");
        }
        const quantity = parseOptionalNumber(lineItem.quantity);
        const unitPrice = parseOptionalNumber(lineItem.unit_price);
        const amount = calculateCustomLineAmount(lineItem);
        if (quantity == null && unitPrice != null) {
          throw new Error(`Add a quantity for "${description}" or clear the unit price.`);
        }
        if (quantity != null && unitPrice == null) {
          throw new Error(`Add a unit price for "${description}" or clear the quantity.`);
        }
        if (amount == null) {
          throw new Error(`Add an amount for "${description}" or provide quantity and unit price.`);
        }
        return {
          description,
          quantity,
          unit_price: unitPrice,
          amount,
        };
      });

    if (customLineItems.length === 0) {
      throw new Error("Add at least one custom line item before creating the invoice.");
    }

    return {
      company_key: form.company_key,
      sender_mailbox: form.sender_mailbox,
      recipient_email: form.recipient_email.trim(),
      cc_email: form.cc_email.trim() || null,
      bill_to_name: form.bill_to_name.trim(),
      bill_to_phone: form.bill_to_phone.trim() || null,
      bill_to_address: form.bill_to_address.trim(),
      issue_date: form.issue_date,
      due_date: form.due_date,
      memo: form.memo.trim(),
      pay_online_label: form.pay_online_label.trim() || null,
      pay_online_url: form.pay_online_url.trim() || null,
      invoice_number_override: form.invoice_number_override.trim() || null,
      composition_mode: "custom",
      currency: form.currency,
      custom_line_items: customLineItems,
    };
  }

  const hourlyRate = parseOptionalNumber(form.hourly_rate);
  const week1Hours = parseOptionalNumber(form.week_1_hours);
  const week2Hours = parseOptionalNumber(form.week_2_hours);
  if (hourlyRate == null) {
    throw new Error("Hourly rate is required.");
  }
  if (week1Hours == null || week2Hours == null) {
    throw new Error("Both weekly hour values are required.");
  }

  return {
    company_key: form.company_key,
    sender_mailbox: form.sender_mailbox,
    recipient_email: form.recipient_email.trim(),
    cc_email: form.cc_email.trim() || null,
    bill_to_name: form.bill_to_name.trim(),
    bill_to_phone: form.bill_to_phone.trim() || null,
    bill_to_address: form.bill_to_address.trim(),
    issue_date: form.issue_date,
    due_date: form.due_date,
    memo: form.memo.trim(),
    pay_online_label: form.pay_online_label.trim() || null,
    pay_online_url: form.pay_online_url.trim() || null,
    invoice_number_override: form.invoice_number_override.trim() || null,
    composition_mode: "time_entry",
    currency: form.currency,
    hourly_rate: hourlyRate,
    week_1_ending: form.week_1_ending,
    week_1_hours: week1Hours,
    week_2_ending: form.week_2_ending,
    week_2_hours: week2Hours,
    custom_line_items: [],
  };
}

type BillingPageProps = {
  currentUser: AuthUser;
};

export default function BillingPage({ currentUser }: BillingPageProps) {
  const [defaultsResponse, setDefaultsResponse] = useState<InvoiceDefaults | null>(null);
  const [form, setForm] = useState<BillingFormState | null>(null);
  const [loadingDefaults, setLoadingDefaults] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [draftResult, setDraftResult] = useState<InvoiceDraftResult | null>(null);
  const [submittingAction, setSubmittingAction] = useState<"render" | "draft" | null>(null);

  useEffect(() => {
    void loadDefaults();
  }, []);

  async function loadDefaults(companyKey?: string) {
    setLoadingDefaults(true);
    setErrorMessage("");
    setStatusMessage("");
    setDraftResult(null);
    try {
      const response = await getInvoiceDefaults(companyKey);
      setDefaultsResponse(response);
      setForm(buildFormFromDefaults(response.defaults));
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setLoadingDefaults(false);
    }
  }

  function updateField<Key extends keyof BillingFormState>(field: Key, value: BillingFormState[Key]) {
    setForm((current) => (current ? { ...current, [field]: value } : current));
  }

  function updateCustomLineItem(
    lineItemId: string,
    field: keyof Omit<BillingLineItemForm, "id">,
    value: string,
  ) {
    setForm((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        custom_line_items: current.custom_line_items.map((lineItem) =>
          lineItem.id === lineItemId ? { ...lineItem, [field]: value } : lineItem,
        ),
      };
    });
  }

  function addCustomLineItem() {
    setForm((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        custom_line_items: [...current.custom_line_items, createLineItemRow()],
      };
    });
  }

  function removeCustomLineItem(lineItemId: string) {
    setForm((current) => {
      if (!current) {
        return current;
      }
      const remaining = current.custom_line_items.filter((lineItem) => lineItem.id !== lineItemId);
      return {
        ...current,
        custom_line_items: remaining.length > 0 ? remaining : [createLineItemRow()],
      };
    });
  }

  async function handleDownloadOnly() {
    if (!form) {
      return;
    }
    setSubmittingAction("render");
    setErrorMessage("");
    setStatusMessage("");
    setDraftResult(null);
    try {
      const payload = buildPayload(form);
      await downloadRenderedInvoice(payload);
      setStatusMessage("Invoice PDF downloaded.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setSubmittingAction(null);
    }
  }

  async function handleCreateDraft() {
    if (!form) {
      return;
    }
    setSubmittingAction("draft");
    setErrorMessage("");
    setStatusMessage("");
    try {
      const payload = buildPayload(form);
      const result = await createInvoiceDraft(payload);
      setDraftResult(result);
      await downloadGeneratedInvoice(result.download_url, result.output_filename);
      setStatusMessage("Draft created in Gmail and the invoice PDF downloaded. The email was drafted, not sent.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setSubmittingAction(null);
    }
  }

  if (loadingDefaults && !form) {
    return (
      <section className="panel auth-panel">
        <p className="empty-state">Loading billing defaults...</p>
      </section>
    );
  }

  if (!form || !defaultsResponse) {
    return (
      <section className="panel auth-panel">
        <p className="empty-state">{errorMessage || "Billing defaults could not be loaded."}</p>
      </section>
    );
  }

  const preview = calculatePreview(form);
  const selectedMailbox: InvoiceSenderMailbox | undefined = defaultsResponse.sender_mailboxes.find(
    (mailbox) => mailbox.email === form.sender_mailbox,
  );
  const isAdminUser = currentUser.is_admin;
  const draftReady = Boolean(selectedMailbox?.draft_enabled);

  return (
    <>
      <section className="grid billing-grid">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Billing</p>
              <h2>Prepare invoice</h2>
            </div>
          </div>

          <p className="panel-subcopy">
            Generate the LeCrown PDF from the platform backend and optionally create a Gmail draft with the PDF already
            attached.
          </p>

          {errorMessage ? <div className="message-banner auth-banner">{errorMessage}</div> : null}
          {statusMessage ? <div className="message-banner">{statusMessage}</div> : null}
          {!isAdminUser ? (
            <div className="message-banner auth-banner">
              You can view the billing workflow, but invoice generation and Gmail draft creation are currently admin-only.
            </div>
          ) : null}

          <div className="content-form">
            <div className="billing-field-grid">
              <label>
                <span>Company</span>
                <select
                  value={form.company_key}
                  onChange={(event) => {
                    void loadDefaults(event.target.value);
                  }}
                  disabled={loadingDefaults || submittingAction !== null}
                >
                  {defaultsResponse.companies.map((company) => (
                    <option key={company.key} value={company.key}>
                      {company.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Sender mailbox</span>
                <select
                  value={form.sender_mailbox}
                  onChange={(event) => updateField("sender_mailbox", event.target.value)}
                  disabled={submittingAction !== null}
                >
                  {defaultsResponse.sender_mailboxes.map((mailbox) => (
                    <option key={mailbox.email} value={mailbox.email}>
                      {mailbox.label}
                      {mailbox.draft_enabled ? "" : " (draft unavailable)"}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                <span>Composition mode</span>
                <select
                  value={form.composition_mode}
                  onChange={(event) =>
                    updateField("composition_mode", event.target.value as InvoiceCompositionMode)
                  }
                  disabled={submittingAction !== null}
                >
                  <option value="time_entry">Time-entry</option>
                  <option value="custom">Custom line items</option>
                </select>
              </label>
            </div>

            <div className="billing-field-grid">
              <label>
                <span>Recipient email</span>
                <input
                  type="email"
                  value={form.recipient_email}
                  onChange={(event) => updateField("recipient_email", event.target.value)}
                  placeholder="recipient@example.com"
                />
              </label>

              <label>
                <span>CC email</span>
                <input
                  type="email"
                  value={form.cc_email}
                  onChange={(event) => updateField("cc_email", event.target.value)}
                  placeholder="Optional CC"
                />
              </label>

              <label>
                <span>Invoice number override</span>
                <input
                  value={form.invoice_number_override}
                  onChange={(event) => updateField("invoice_number_override", event.target.value)}
                  placeholder="Auto-generate if blank"
                />
              </label>
            </div>

            <div className="billing-field-grid">
              <label>
                <span>Bill-to name</span>
                <input
                  value={form.bill_to_name}
                  onChange={(event) => updateField("bill_to_name", event.target.value)}
                  placeholder="Client or company name"
                />
              </label>

              <label>
                <span>Bill-to phone</span>
                <input
                  value={form.bill_to_phone}
                  onChange={(event) => updateField("bill_to_phone", event.target.value)}
                  placeholder="Optional phone"
                />
              </label>

              <label>
                <span>Currency</span>
                <input value={form.currency} disabled />
              </label>
            </div>

            <label>
              <span>Bill-to address</span>
              <textarea
                rows={4}
                value={form.bill_to_address}
                onChange={(event) => updateField("bill_to_address", event.target.value)}
                placeholder="Street&#10;City, State ZIP"
              />
            </label>

            <div className="billing-field-grid">
              <label>
                <span>Issue date</span>
                <input
                  type="date"
                  value={form.issue_date}
                  onChange={(event) => updateField("issue_date", event.target.value)}
                />
              </label>

              <label>
                <span>Due date</span>
                <input
                  type="date"
                  value={form.due_date}
                  onChange={(event) => updateField("due_date", event.target.value)}
                />
              </label>

              <label>
                <span>Pay-online label</span>
                <input
                  value={form.pay_online_label}
                  onChange={(event) => updateField("pay_online_label", event.target.value)}
                  placeholder="Optional"
                />
              </label>
            </div>

            <label>
              <span>Pay-online URL</span>
              <input
                type="url"
                value={form.pay_online_url}
                onChange={(event) => updateField("pay_online_url", event.target.value)}
                placeholder="https://"
              />
            </label>

            <label>
              <span>Memo</span>
              <textarea
                rows={4}
                value={form.memo}
                onChange={(event) => updateField("memo", event.target.value)}
                placeholder="Description shown on the invoice and in the draft email"
              />
            </label>

            {form.composition_mode === "time_entry" ? (
              <section className="billing-section">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">Time Entry</p>
                    <h2>Two-week invoice composition</h2>
                  </div>
                </div>

                <div className="billing-field-grid">
                  <label>
                    <span>Hourly rate</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.hourly_rate}
                      onChange={(event) => updateField("hourly_rate", event.target.value)}
                    />
                  </label>

                  <label>
                    <span>Week 1 ending</span>
                    <input
                      type="date"
                      value={form.week_1_ending}
                      onChange={(event) => updateField("week_1_ending", event.target.value)}
                    />
                  </label>

                  <label>
                    <span>Week 1 hours</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.week_1_hours}
                      onChange={(event) => updateField("week_1_hours", event.target.value)}
                    />
                  </label>

                  <label>
                    <span>Week 2 ending</span>
                    <input
                      type="date"
                      value={form.week_2_ending}
                      onChange={(event) => updateField("week_2_ending", event.target.value)}
                    />
                  </label>

                  <label>
                    <span>Week 2 hours</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.week_2_hours}
                      onChange={(event) => updateField("week_2_hours", event.target.value)}
                    />
                  </label>
                </div>
              </section>
            ) : (
              <section className="billing-section">
                <div className="panel-heading">
                  <div>
                    <p className="eyebrow">Line Items</p>
                    <h2>Custom invoice rows</h2>
                  </div>
                  <button type="button" className="secondary-link" onClick={addCustomLineItem}>
                    Add row
                  </button>
                </div>

                <p className="panel-subcopy">
                  Quantity and unit price are optional. If both are filled, the row amount is calculated automatically.
                  Rows labeled <strong>Tax</strong> are excluded from subtotal and added into total.
                </p>

                <div className="billing-line-item-stack">
                  {form.custom_line_items.map((lineItem) => (
                    <div className="billing-line-item-row" key={lineItem.id}>
                      <label className="billing-line-item-description">
                        <span>Description</span>
                        <input
                          value={lineItem.description}
                          onChange={(event) =>
                            updateCustomLineItem(lineItem.id, "description", event.target.value)
                          }
                          placeholder="Describe the work, material, or tax line"
                        />
                      </label>
                      <label>
                        <span>Qty</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={lineItem.quantity}
                          onChange={(event) =>
                            updateCustomLineItem(lineItem.id, "quantity", event.target.value)
                          }
                          placeholder="Optional"
                        />
                      </label>
                      <label>
                        <span>Unit price</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={lineItem.unit_price}
                          onChange={(event) =>
                            updateCustomLineItem(lineItem.id, "unit_price", event.target.value)
                          }
                          placeholder="Optional"
                        />
                      </label>
                      <label>
                        <span>Amount</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={lineItem.amount}
                          onChange={(event) =>
                            updateCustomLineItem(lineItem.id, "amount", event.target.value)
                          }
                          placeholder="Required if qty/unit price are blank"
                        />
                      </label>
                      <button
                        type="button"
                        className="secondary-link destructive-button billing-remove-line-item"
                        onClick={() => removeCustomLineItem(lineItem.id)}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {!draftReady ? (
              <p className="panel-subcopy">
                The selected mailbox does not have Gmail draft credentials configured yet. PDF download still works.
              </p>
            ) : null}

            <div className="action-row billing-actions">
              <button
                type="button"
                onClick={() => void handleCreateDraft()}
                disabled={!isAdminUser || !draftReady || submittingAction !== null}
              >
                {submittingAction === "draft" ? "Creating draft..." : "Create Draft + Download PDF"}
              </button>
              <button
                type="button"
                className="secondary-link"
                onClick={() => void handleDownloadOnly()}
                disabled={!isAdminUser || submittingAction !== null}
              >
                {submittingAction === "render" ? "Downloading..." : "Download PDF Only"}
              </button>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Preview</p>
              <h2>Live invoice summary</h2>
            </div>
          </div>

          <div className="billing-preview-card">
            <div className="billing-preview-meta">
              <div>
                <span className="billing-preview-label">Invoice number</span>
                <strong>{form.invoice_number_override.trim() || "Assigned on generation"}</strong>
              </div>
              <div>
                <span className="billing-preview-label">Company</span>
                <strong>
                  {defaultsResponse.companies.find((company) => company.key === form.company_key)?.label ?? form.company_key}
                </strong>
              </div>
              <div>
                <span className="billing-preview-label">Issue date</span>
                <strong>{formatLongDate(form.issue_date)}</strong>
              </div>
              <div>
                <span className="billing-preview-label">Due date</span>
                <strong>{formatLongDate(form.due_date)}</strong>
              </div>
            </div>

            <div className="profile-stat-grid billing-stat-grid">
              <div className="metric-pill">
                <strong>{formatCurrency(preview.subtotal, form.currency)}</strong>
                <span>subtotal</span>
              </div>
              <div className="metric-pill">
                <strong>{formatCurrency(preview.total, form.currency)}</strong>
                <span>total</span>
              </div>
              <div className="metric-pill">
                <strong>{formatCurrency(preview.amountDue, form.currency)}</strong>
                <span>amount due</span>
              </div>
              <div className="metric-pill">
                <strong>{selectedMailbox?.email ?? form.sender_mailbox}</strong>
                <span>mailbox</span>
              </div>
            </div>

            <div className="billing-preview-routing">
              <span>
                <strong>To:</strong> {form.recipient_email || "No recipient set"}
              </span>
              {form.cc_email.trim() ? (
                <span>
                  <strong>CC:</strong> {form.cc_email}
                </span>
              ) : null}
            </div>

            <div className="billing-preview-lines">
              {preview.lineItems.length === 0 ? (
                <p className="empty-state">No line items yet.</p>
              ) : (
                preview.lineItems.map((lineItem, index) => (
                  <div className="billing-preview-line" key={`${lineItem.description}-${index}`}>
                    <div>
                      <strong>{lineItem.description}</strong>
                      <span>
                        {lineItem.quantity != null && lineItem.unit_price != null
                          ? `${lineItem.quantity} x ${formatCurrency(lineItem.unit_price, form.currency)}`
                          : lineItem.subtotal_included
                            ? "Included in subtotal"
                            : "Excluded from subtotal"}
                      </span>
                    </div>
                    <strong>{formatCurrency(lineItem.amount, form.currency)}</strong>
                  </div>
                ))
              )}
            </div>
          </div>

          {draftResult ? (
            <div className="billing-success-card">
              <div>
                <p className="eyebrow">Draft Ready</p>
                <h2>Invoice drafted in Gmail</h2>
              </div>

              <div className="billing-success-grid">
                <div>
                  <span>Invoice number</span>
                  <strong>{draftResult.invoice_number}</strong>
                </div>
                <div>
                  <span>PDF filename</span>
                  <strong>{draftResult.output_filename}</strong>
                </div>
                <div>
                  <span>Mailbox used</span>
                  <strong>{draftResult.sender_mailbox}</strong>
                </div>
                <div>
                  <span>Recipient</span>
                  <strong>{draftResult.recipient_email}</strong>
                </div>
                {draftResult.cc_email ? (
                  <div>
                    <span>CC</span>
                    <strong>{draftResult.cc_email}</strong>
                  </div>
                ) : null}
                <div>
                  <span>Gmail draft id</span>
                  <strong>{draftResult.gmail_draft_id}</strong>
                </div>
              </div>

              <p className="panel-subcopy">
                The invoice email was created as a draft only. Nothing was sent automatically.
              </p>
            </div>
          ) : null}
        </article>
      </section>
    </>
  );
}
