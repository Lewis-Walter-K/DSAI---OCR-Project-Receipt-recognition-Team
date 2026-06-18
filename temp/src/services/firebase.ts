import { initializeApp } from 'firebase/app';
import { getDatabase } from 'firebase/database';

// Uses fake config except for databaseURL which we know is public for this project
const firebaseConfig = {
  apiKey: "fake_api_key",
  authDomain: "wo-ist-mein-geld-24416.firebaseapp.com",
  databaseURL: "https://wo-ist-mein-geld-24416-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "wo-ist-mein-geld-24416",
  storageBucket: "wo-ist-mein-geld-24416.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abcdef"
};

const app = initializeApp(firebaseConfig);
export const db = getDatabase(app);
