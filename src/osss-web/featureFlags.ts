// src/osss-web/featureFlags.ts

// Add a key here for each module you want to toggle
export type FeatureFlagKey =
  | "activities"
  | "schoolBoard"
  // | "transportation"
  // | "aiMentor"
  ;

type FeatureFlags = Record<FeatureFlagKey, boolean>;

// Helper to parse env vars safely
function envFlag(name: string, defaultValue: boolean = false): boolean {
  const value = process.env[name];
  if (!value) return defaultValue;
  return value.toLowerCase() === "true" || value === "1" || value.toLowerCase() === "yes";
}

export const featureFlags: FeatureFlags = {
  activities: envFlag("NEXT_PUBLIC_FEATURE_ACTIVITIES", true),
  schoolBoard: envFlag("NEXT_PUBLIC_FEATURE_SCHOOL_BOARD", true),
};

export function isFeatureEnabled(flag: FeatureFlagKey): boolean {
  return featureFlags[flag];
}
