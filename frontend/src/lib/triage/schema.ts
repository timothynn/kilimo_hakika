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

/** 6 digits. Short enough to type on a keypad, so the endpoint is rate limited. */
const pinSchema = z
  .string()
  .regex(/^\d{6}$/, "Your PIN must be exactly 6 digits");

const phoneSchema = z
  .string()
  .trim()
  .regex(/^(?:\+254|0)7\d{8}$/, "Enter a phone number like 0712345678");

export const farmerSignInSchema = z.object({
  phone: phoneSchema,
  pin: pinSchema,
});

export const farmerSignUpSchema = z
  .object({
    fullName: z.string().trim().min(2, "Enter your full name").max(120),
    nationalId: nationalIdSchema,
    phone: phoneSchema,
    county: z.string().trim().min(2, "Enter your county").max(60),
    acres: z
      .number()
      .positive("Land size must be greater than zero")
      .max(1000),
    pin: pinSchema,
    confirmPin: z.string(),
    consentGiven: z.literal(true, {
      message: "You must agree before we store your details",
    }),
  })
  .refine((data) => data.pin === data.confirmPin, {
    message: "The two PINs do not match",
    path: ["confirmPin"],
  });

export type FarmerSignUpPayload = z.infer<typeof farmerSignUpSchema>;

export const farmerRegistrationSchema = z.object({
  fullName: z.string().trim().min(2, "Enter the farmer's full name").max(120),
  nationalId: nationalIdSchema,
  phone: phoneSchema,
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
