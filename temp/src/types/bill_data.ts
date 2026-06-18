export interface Bill {
  id?: string;
  bill_purpose: string;
  bill_date: string;
  timestamp_created: number;
  original_value: number;
  original_currency: string;
  total_bill_value: number;
  converted: boolean;
}

export interface UserSettings {
  region: string;
  base_currency: string;
}

export interface UserData {
  settings: UserSettings;
  bills: Record<string, Bill>;
}

// Dummy constants to fix Vite/Rolldown type-only export bug
export const _DUMMY = true;
