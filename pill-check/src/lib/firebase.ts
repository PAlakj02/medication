// Firebase Auth — login gate only. No Firestore/Realtime Database usage:
// we deliberately never persist per-user data (see project decision to
// keep the backend stateless per-request). This file only produces an
// identity and an ID token to attach to backend requests.
//
// Email/password, not Google OAuth — the OAuth popup/redirect flow proved
// unreliable across Safari Private Browsing and iOS in practice (blocked
// popups, authorized-domain edge cases). Email/password is a direct SDK
// call with no cross-origin redirect involved.

import { initializeApp } from "firebase/app";
import {
  createUserWithEmailAndPassword,
  getAuth,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  updateProfile,
  type User,
} from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env["VITE_FIREBASE_API_KEY"],
  authDomain: import.meta.env["VITE_FIREBASE_AUTH_DOMAIN"],
  projectId: import.meta.env["VITE_FIREBASE_PROJECT_ID"],
  storageBucket: import.meta.env["VITE_FIREBASE_STORAGE_BUCKET"],
  messagingSenderId: import.meta.env["VITE_FIREBASE_MESSAGING_SENDER_ID"],
  appId: import.meta.env["VITE_FIREBASE_APP_ID"],
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

export type { User };

export function onAuthChange(callback: (user: User | null) => void): () => void {
  return onAuthStateChanged(auth, callback);
}

export async function signUpWithEmail(email: string, password: string, name: string): Promise<void> {
  // displayName lives on Firebase's own user record, same as the email
  // already does — not our backend/database, so this doesn't change the
  // "we don't store medication or user data ourselves" decision.
  const credential = await createUserWithEmailAndPassword(auth, email, password);
  const trimmedName = name.trim();
  if (trimmedName) {
    await updateProfile(credential.user, { displayName: trimmedName });
  }
}

export async function signInWithEmail(email: string, password: string): Promise<void> {
  await signInWithEmailAndPassword(auth, email, password);
}

export async function signOut(): Promise<void> {
  await firebaseSignOut(auth);
}

export function getCurrentIdToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return Promise.resolve(null);
  return user.getIdToken();
}
