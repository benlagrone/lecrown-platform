export type TrecFormCategory = "Contracts" | "Contract Addenda" | "Other Forms";

export type TrecForm = {
  category: TrecFormCategory;
  title: string;
  formId: string;
  effectiveDate: string;
  trecPageUrl: string;
  trecPdfUrl: string;
  driveUrl?: string;
};

export const TREC_FORMS_RETRIEVED_AT = "2026-09-01";
export const TREC_FORMS_SOURCE_URL = "https://www.trec.texas.gov/node/34";
export const TREC_DRIVE_LIBRARY_URL: string | null = null;

export const TREC_FORMS: TrecForm[] = [
  {
    "category": "Contracts",
    "title": "Amendment to Contract",
    "formId": "39-11",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/amendment",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/39-11.pdf"
  },
  {
    "category": "Contracts",
    "title": "Farm and Ranch Contract",
    "formId": "25-17",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/farm-and-ranch-contract-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/25-17_4.pdf"
  },
  {
    "category": "Contracts",
    "title": "New Home Contract (Completed Construction)",
    "formId": "24-20",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/new-home-contract-completed-construction-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/24-20_0.pdf"
  },
  {
    "category": "Contracts",
    "title": "New Home Contract (Incomplete Construction)",
    "formId": "23-20",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/new-home-contract-incomplete-construction-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/23-20_3.pdf"
  },
  {
    "category": "Contracts",
    "title": "One to Four Family Residential Contract (Resale)",
    "formId": "20-19",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/one-four-family-residential-contract-resale",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/20-19_4.pdf"
  },
  {
    "category": "Contracts",
    "title": "Residential Condominium Contract (Resale)",
    "formId": "30-18",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/residential-condominium-contract-resale-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/30-18_0.pdf"
  },
  {
    "category": "Contracts",
    "title": "Unimproved Property Contract",
    "formId": "9-18",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/unimproved-property-contract-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/9-18_1.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum Concerning Right to Terminate Due to Lender's Appraisal",
    "formId": "49-1",
    "effectiveDate": "03/01/2019",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-concerning-right-terminate-due-lenders-appraisal-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/49-1.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum Containing Notice of Obligation to Pay Improvement District Assessment",
    "formId": "53-0",
    "effectiveDate": "09/01/2021",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-containing-notice-obligation-pay-improvement-district-assesment",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/53-0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for \"Back-Up\" Contract",
    "formId": "11-9",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-back-contract",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/11-9.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Authorizing Hydrostatic Testing",
    "formId": "48-1",
    "effectiveDate": "03/01/2020",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-authorizing-hydrostatic-testing-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/48-1.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Coastal Area Property",
    "formId": "33-2",
    "effectiveDate": "12/05/2011",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-coastal-area-property",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/33-2.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Property in a Propane Gas System Service Area",
    "formId": "47-0",
    "effectiveDate": "02/01/2014",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-property-propane-gas-system-service-area",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/47-0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Property Located Seaward of the Gulf Intracoastal Waterway",
    "formId": "34-4",
    "effectiveDate": "12/05/2011",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-property-located-seaward-gulf-intercoastal-waterway",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/34-4.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Property Subject to Mandatory Membership in a Property Owners Association",
    "formId": "36-11",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-property-subject-mandatory-membership-property-owners-association",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/36-11.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Release of Liability on Assumed Loan and/or Restoration of Seller's VA Entitlement",
    "formId": "12-3",
    "effectiveDate": "12/05/2011",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-release-liability-assumed-loan-andor-restoration-sellers-va-entitlement",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/12-3_0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Reservation of Oil, Gas, and Other Minerals",
    "formId": "44-3",
    "effectiveDate": "02/01/2023",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-reservation-oil-gas-and-other-minerals-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/44-3_0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Sale of Other Property by Buyer",
    "formId": "10-6",
    "effectiveDate": "12/05/2011",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-sale-other-property-buyer",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/10-6.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Section 1031 Exchange",
    "formId": "60-0",
    "effectiveDate": "01/03/2025",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-section-1031-exchange",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/60-0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum for Seller's Disclosure of Information on Lead-Based Paint and Lead-Based Paint Hazards as Required by Federal Law",
    "formId": "56-0",
    "effectiveDate": "05/28/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-sellers-disclosure-information-lead-based-paint-and-lead-based-paint-hazards-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/56-0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum Regarding Fixture Leases",
    "formId": "52-1",
    "effectiveDate": "02/01/2023",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-regarding-fixture-leases-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/52-1_0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Addendum Regarding Residential Leases",
    "formId": "51-1",
    "effectiveDate": "02/01/2023",
    "trecPageUrl": "https://www.trec.texas.gov/forms/addendum-regarding-residential-leases-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/51-1_0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Buyer's Temporary Residential Lease",
    "formId": "16-7",
    "effectiveDate": "01/05/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/buyers-temporary-residential-lease",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/16-7.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Environmental Assessment, Threatened of Endangered Species, and Wetlands Addendum",
    "formId": "28-2",
    "effectiveDate": "12/05/2011",
    "trecPageUrl": "https://www.trec.texas.gov/forms/environmental-assessment-threatened-endangered-species-and-wetlands-addendum",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/28-2.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Loan Assumption Addendum",
    "formId": "41-3",
    "effectiveDate": "02/01/2023",
    "trecPageUrl": "https://www.trec.texas.gov/forms/loan-assumption-addendum-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/41-3_0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Non-Realty Items Addendum",
    "formId": "57-0",
    "effectiveDate": "09/03/2025",
    "trecPageUrl": "https://www.trec.texas.gov/forms/non-realty-items-addendum",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/57-0_1.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Seller Financing Addendum",
    "formId": "26-8",
    "effectiveDate": "02/01/2023",
    "trecPageUrl": "https://www.trec.texas.gov/forms/seller-financing-addendum-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/26-8_0.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Seller's Temporary Residential Lease",
    "formId": "15-7",
    "effectiveDate": "01/05/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/sellers-temporary-residential-lease",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/15-7.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Short Sale Addendum",
    "formId": "45-2",
    "effectiveDate": "04/01/2021",
    "trecPageUrl": "https://www.trec.texas.gov/forms/short-sale-addendum-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/45-2_1.pdf"
  },
  {
    "category": "Contract Addenda",
    "title": "Third Party Financing Addendum",
    "formId": "40-11",
    "effectiveDate": "01/03/2025",
    "trecPageUrl": "https://www.trec.texas.gov/forms/third-party-financing-addendum-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/40-11.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Condominium Resale Certificate",
    "formId": "32-5",
    "effectiveDate": "11/25/2024",
    "trecPageUrl": "https://www.trec.texas.gov/forms/condominium-resale-certificate-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/32-5.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Disclosure of Relationship with Residential Service Company",
    "formId": "RSC-4",
    "effectiveDate": "06/11/2023",
    "trecPageUrl": "https://www.trec.texas.gov/forms/disclosure-relationship-residential-service-company",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/RSC-4_1.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Landlord's Floodplain and Flood Notice",
    "formId": "54-1",
    "effectiveDate": "11/26/2025",
    "trecPageUrl": "https://www.trec.texas.gov/forms/landlords-floodplain-and-flood-notice-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/54-1.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Notice of Buyer's Termination of Contract",
    "formId": "38-8",
    "effectiveDate": "04/01/2025",
    "trecPageUrl": "https://www.trec.texas.gov/forms/notice-buyers-termination-contract",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/38-8.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Notice of Seller's Termination of Contract",
    "formId": "50-0",
    "effectiveDate": "08/13/2018",
    "trecPageUrl": "https://www.trec.texas.gov/forms/notice-sellers-termination-contract",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/50-0.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Notice to Prospective Buyer",
    "formId": "58-0",
    "effectiveDate": "09/03/2025",
    "trecPageUrl": "https://www.trec.texas.gov/forms/notice-prospective-buyer-0",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/58-0.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Notice to Purchaser of Special Taxing or Assessment District",
    "formId": "59-0",
    "effectiveDate": "02/12/2024",
    "trecPageUrl": "https://www.trec.texas.gov/forms/notice-purchaser-special-taxing-or-assessment-district",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/59-0_0.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Property Inspection Report",
    "formId": "REI 7-6",
    "effectiveDate": "02/01/2022",
    "trecPageUrl": "https://www.trec.texas.gov/forms/inspection-report-form",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/REI%207-6_fillable.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Seller's Disclosure about Groundwater and Surface Water Rights",
    "formId": "61-0",
    "effectiveDate": "07/01/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/water-notice-sellers-disclosure-about-groundwater-and-surface-water-rights",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/61-0.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Seller's Disclosure Notice",
    "formId": "55-1",
    "effectiveDate": "05/28/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/sellers-disclosure-notice",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/55-1.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Seller's Notice to Buyer of Removal of Contingency Under Addendum for \"Back-Up\" Contract",
    "formId": "62-0",
    "effectiveDate": "05/28/2026",
    "trecPageUrl": "https://www.trec.texas.gov/forms/sellers-notice-buyer-removal-contingency-under-addendum-back-contract",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/62-0.pdf"
  },
  {
    "category": "Other Forms",
    "title": "Subdivision Information, Including Resale Certificate for Property Subject to Mandatory Membership in a Property Owners' Association",
    "formId": "37-5",
    "effectiveDate": "02/10/2014",
    "trecPageUrl": "https://www.trec.texas.gov/forms/subdivision-information-including-resale-certificate-property-subject-mandatory-membership",
    "trecPdfUrl": "https://www.trec.texas.gov/sites/default/files/pdf-forms/37-5.pdf"
  }
];

