import { ref, push, set, onValue, query, limitToLast } from 'firebase/database';
import { db } from './firebase';
import type { Bill, UserSettings } from '../types/bill_data';

const USER_ID = 'default_user'; // Based on GEMINI.md "user_id_cố_định"

export const billService = {
  saveBill: async (bill: Bill) => {
    const billsRef = ref(db, `users/${USER_ID}/bills`);
    const newBillRef = push(billsRef);
    return set(newBillRef, bill);
  },

  getSettings: (callback: (settings: UserSettings) => void) => {
    const settingsRef = ref(db, `users/${USER_ID}/settings`);
    return onValue(settingsRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        callback(data);
      } else {
        // Default settings
        callback({ region: 'VN', base_currency: 'VND' });
      }
    });
  },

  updateSettings: (settings: UserSettings) => {
    const settingsRef = ref(db, `users/${USER_ID}/settings`);
    return set(settingsRef, settings);
  },

  subscribeToBills: (callback: (bills: Bill[]) => void) => {
    const billsRef = ref(db, `users/${USER_ID}/bills`);
    const billsQuery = query(billsRef, limitToLast(100)); // Limit to last 100
    return onValue(billsQuery, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const billsList = Object.entries(data).map(([id, bill]) => ({
          ...(bill as Bill),
          id
        }));
        callback(billsList);
      } else {
        callback([]);
      }
    });
  },

  // Test function to push hello as requested
  testFirebase: async () => {
    const testRef = ref(db, 'test_sdk');
    await set(testRef, 'hello');
    console.log('Successfully pushed "hello" to Firebase RTDB test node!');
  }
};
