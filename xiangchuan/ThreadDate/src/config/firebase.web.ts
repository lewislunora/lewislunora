// Web-compatible Firebase config (Replit / browser environments)
import { initializeApp } from 'firebase/app'
import { getAuth, connectAuthEmulator } from 'firebase/auth'
import { getFirestore, connectFirestoreEmulator } from 'firebase/firestore'
import { getStorage } from 'firebase/storage'

const firebaseConfig = {
  apiKey: 'YOUR_API_KEY',
  authDomain: 'YOUR_PROJECT.firebaseapp.com',
  projectId: 'YOUR_PROJECT_ID',
  storageBucket: 'YOUR_PROJECT.appspot.com',
  messagingSenderId: 'YOUR_SENDER_ID',
  appId: 'YOUR_APP_ID',
}

let initialized = false

export function initFirebase(config?: typeof firebaseConfig, useEmulator?: boolean) {
  if (initialized) return
  const cfg = config || firebaseConfig
  const app = initializeApp(cfg)
  const auth = getAuth(app)
  const db = getFirestore(app)
  const storage = getStorage(app)

  if (useEmulator) {
    connectAuthEmulator(auth, 'http://localhost:9099')
    connectFirestoreEmulator(db, 'localhost', 8080)
  }

  initialized = true
  return { app, auth, db, storage }
}
