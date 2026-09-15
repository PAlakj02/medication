// Firebase Auth — login gate only. No Firestore/Realtime Database usage:
// we deliberately never persist per-user data (see project decision to
// keep the backend stateless per-request). This file only produces an
// identity and an ID token to attach to backend requests.

import { initializeApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  getRedirectResult,
  onAuthStateChanged,
  signInWithRedirect,
  signOut as firebaseSignOut,
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
const googleProvider = new GoogleAuthProvider();

export type { User };

export function onAuthChange(callback: (user: User | null) => void): () => void {
  return onAuthStateChanged(auth, callback);
}

export async function signInWithGoogle(): Promise<void> {
  // Redirect, not popup — popups get silently blocked by Safari Private
  // Browsing and many mobile browsers, which reads to users as a generic
  // "sign-in failed" with no clear cause. Redirect is a full navigation,
  // so it isn't subject to popup/third-party-storage restrictions.
  await signInWithRedirect(auth, googleProvider);
}

// Call once on app load: after signInWithGoogle() redirects back, this
// resolves with the signed-in user (or null if the user just landed here
// normally, not returning from a redirect). Throws if the redirect flow
// itself failed (e.g. domain not authorized in Firebase).
export function consumeRedirectResult(): Promise<User | null> {
  return getRedirectResult(auth).then((result) => result?.user ?? null);
}

export async function signOut(): Promise<void> {
  await firebaseSignOut(auth);
}

export function getCurrentIdToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return Promise.resolve(null);
  return user.getIdToken();
}
