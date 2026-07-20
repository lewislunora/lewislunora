import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
  User,
  UserCredential,
} from 'firebase/auth'
import { doc, setDoc, getDoc, serverTimestamp } from 'firebase/firestore'
import { getFirebaseApp } from '../config/firebase'

export async function registerWithEmail(
  email: string,
  password: string,
  displayName: string,
  birthDate: string,
  gender: string,
  bio?: string
): Promise<User> {
  const { auth, db } = getFirebaseApp()
  const cred: UserCredential = await createUserWithEmailAndPassword(auth, email, password)
  const user = cred.user

  await updateProfile(user, { displayName })

  await setDoc(doc(db, 'users', user.uid), {
    uid: user.uid,
    email,
    displayName,
    birthDate,
    gender,
    bio: bio || '',
    photoURL: '',
    interests: [],
    photos: [],
    createdAt: serverTimestamp(),
    lastActive: serverTimestamp(),
    onboardingComplete: false,
  })

  return user
}

export async function loginWithEmail(email: string, password: string): Promise<User> {
  const { auth } = getFirebaseApp()
  const cred = await signInWithEmailAndPassword(auth, email, password)
  return cred.user
}

export async function logout(): Promise<void> {
  const { auth } = getFirebaseApp()
  await signOut(auth)
}

export async function getUserProfile(uid: string) {
  const { db } = getFirebaseApp()
  const snap = await getDoc(doc(db, 'users', uid))
  return snap.exists() ? snap.data() : null
}

export function getCurrentUser(): User | null {
  const { auth } = getFirebaseApp()
  return auth.currentUser
}
