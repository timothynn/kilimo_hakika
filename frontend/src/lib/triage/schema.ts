import { z } from "zod";

/**
 * Input contract for a triage check.
 *
 * The frontend uses this for the wizard form; the API route re-parses the
 * request body with the same schema. Client-side validation is a convenience,
 * never the gate — a verdict must never rest on what the browser claimed.
 */
export const triageInputSchema = z.object({
  acres: z
    .number({ message: "Enter your land size in acres" })
    .positive("Land size must be greater than zero")
    .max(1000, "Enter land size in acres — 1000 is the maximum this tool handles"),
  depotId: z.string().min(1, "Choose the depot you plan to travel to"),
  heldDocuments: z.array(z.string()).default([]),
});

export type TriageInputPayload = z.infer<typeof triageInputSchema>;

/** Kenyan national ID: 7-9 digits in current circulation. */
const nationalIdSchema = z
  .string()
  .trim()
  .regex(/^\d{7,9}$/, "National ID should be 7 to 9 digits");

export const farmerRegistrationSchema = z.object({
  fullName: z.string().trim().min(2, "Enter the farmer's full name").max(120),
  nationalId: nationalIdSchema,
  phone: z
    .string()
    .trim()
    .regex(/^(?:\+254|0)7\d{8}$/, "Enter a phone number like 0712345678"),
  county: z.string().trim().min(2, "Enter the county").max(60),
  acres: z.number().positive("Land size must be greater than zero").max(1000),
  consentGiven: z.literal(true, {
    message: "The farmer must consent before their details are stored",
  }),
});

export type FarmerRegistrationPayload = z.infer<typeof farmerRegistrationSchema>;

/** Depot officer looking a farmer up at the gate. */
export const farmerLookupSchema = z.object({
  nationalId: nationalIdSchema,
});
