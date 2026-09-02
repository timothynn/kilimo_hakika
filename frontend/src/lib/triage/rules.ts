import type { SchemeRules } from "./types";

// Copied from database/scheme_rules.json by scripts/sync-rules.mjs, which
// predev/prebuild/pretest run. Imported statically rather than read from disk
// so the policy is baked into the build and Turbopack does not trace the whole
// project into the server bundle. Edit the file in database/, never this copy.
import rulesJson from "./scheme_rules.json";

const rules = rulesJson as SchemeRules;

export function loadRules(): SchemeRules {
  return rules;
}
