import {
  collection,
  addDoc,
  updateDoc,
  doc,
  getDoc,
  getDocs,
  query,
  where,
  orderBy,
  limit,
  onSnapshot,
  serverTimestamp,
  arrayUnion,
  arrayRemove,
  Timestamp,
  deleteDoc,
  increment,
  Unsubscribe,
} from 'firebase/firestore'
import { getFirebaseApp } from '../config/firebase'

// ─── Threads ───

export interface Thread {
  id?: string
  title: string
  content: string
  tags: string[]
  authorId: string
  authorName: string
  authorPhoto?: string
  anonymous: boolean
  likes: number
  commentCount: number
  createdAt: Timestamp
}

export async function createThread(thread: Omit<Thread, 'id' | 'createdAt' | 'likes' | 'commentCount'>) {
  const { db } = getFirebaseApp()
  return addDoc(collection(db, 'threads'), {
    ...thread,
    likes: 0,
    commentCount: 0,
    createdAt: serverTimestamp(),
  })
}

export function subscribeThreads(callback: (threads: Thread[]) => void): Unsubscribe {
  const { db } = getFirebaseApp()
  const q = query(collection(db, 'threads'), orderBy('createdAt', 'desc'), limit(50))
  return onSnapshot(q, (snap) => {
    const threads: Thread[] = snap.docs.map((d) => ({ id: d.id, ...d.data() } as Thread))
    callback(threads)
  })
}

export async function getThread(threadId: string) {
  const { db } = getFirebaseApp()
  const snap = await getDoc(doc(db, 'threads', threadId))
  return snap.exists() ? { id: snap.id, ...snap.data() } : null
}

export async function toggleLikeThread(threadId: string, userId: string, liked: boolean) {
  const { db } = getFirebaseApp()
  const ref = doc(db, 'threads', threadId)
  if (liked) {
    await updateDoc(ref, { likes: increment(-1) })
  } else {
    await updateDoc(ref, { likes: increment(1) })
  }
}

// ─── Comments ───

export interface Comment {
  id?: string
  threadId: string
  content: string
  authorId: string
  authorName: string
  authorPhoto?: string
  anonymous: boolean
  createdAt: Timestamp
}

export async function addComment(comment: Omit<Comment, 'id' | 'createdAt'>) {
  const { db } = getFirebaseApp()
  const ref = await addDoc(collection(db, 'comments'), {
    ...comment,
    createdAt: serverTimestamp(),
  })
  await updateDoc(doc(db, 'threads', comment.threadId), { commentCount: increment(1) })
  return ref
}

export function subscribeComments(threadId: string, callback: (comments: Comment[]) => void): Unsubscribe {
  const { db } = getFirebaseApp()
  const q = query(
    collection(db, 'comments'),
    where('threadId', '==', threadId),
    orderBy('createdAt', 'asc')
  )
  return onSnapshot(q, (snap) => {
    const comments: Comment[] = snap.docs.map((d) => ({ id: d.id, ...d.data() } as Comment))
    callback(comments)
  })
}

// ─── Likes / Matches ───

export async function likeUser(fromUserId: string, toUserId: string) {
  const { db } = getFirebaseApp()
  await addDoc(collection(db, 'likes'), {
    fromUserId,
    toUserId,
    createdAt: serverTimestamp(),
  })
}

export async function checkMutualLike(userId1: string, userId2: string): Promise<boolean> {
  const { db } = getFirebaseApp()
  const q1 = query(
    collection(db, 'likes'),
    where('fromUserId', '==', userId1),
    where('toUserId', '==', userId2)
  )
  const q2 = query(
    collection(db, 'likes'),
    where('fromUserId', '==', userId2),
    where('toUserId', '==', userId1)
  )
  const [s1, s2] = await Promise.all([getDocs(q1), getDocs(q2)])
  return !s1.empty && !s2.empty
}

export async function createMatch(userId1: string, userId2: string) {
  const { db } = getFirebaseApp()
  const matchId = [userId1, userId2].sort().join('_')
  await setDoc(doc(db, 'matches', matchId), {
    users: [userId1, userId2],
    createdAt: serverTimestamp(),
    lastMessage: '',
    lastMessageAt: null,
  })
  return matchId
}

// ─── Chat ───

export interface Message {
  id?: string
  matchId: string
  senderId: string
  text: string
  createdAt: Timestamp
}

export async function sendMessage(matchId: string, senderId: string, text: string) {
  const { db } = getFirebaseApp()
  const ref = await addDoc(collection(db, 'messages'), {
    matchId,
    senderId,
    text,
    createdAt: serverTimestamp(),
  })
  await updateDoc(doc(db, 'matches', matchId), {
    lastMessage: text,
    lastMessageAt: serverTimestamp(),
  })
  return ref
}

export function subscribeMessages(matchId: string, callback: (msgs: Message[]) => void): Unsubscribe {
  const { db } = getFirebaseApp()
  const q = query(
    collection(db, 'messages'),
    where('matchId', '==', matchId),
    orderBy('createdAt', 'asc')
  )
  return onSnapshot(q, (snap) => {
    const msgs: Message[] = snap.docs.map((d) => ({ id: d.id, ...d.data() } as Message))
    callback(msgs)
  })
}

export function subscribeMatches(userId: string, callback: (matches: any[]) => void): Unsubscribe {
  const { db } = getFirebaseApp()
  const q = query(
    collection(db, 'matches'),
    where('users', 'array-contains', userId),
    orderBy('lastMessageAt', 'desc')
  )
  return onSnapshot(q, (snap) => {
    const matches = snap.docs.map((d) => ({ id: d.id, ...d.data() }))
    callback(matches)
  })
}

// ─── Discovery ───

export async function getDiscoverUsers(currentUserId: string, limitCount = 20) {
  const { db } = getFirebaseApp()
  const q = query(collection(db, 'users'), limit(limitCount))
  const snap = await getDocs(q)
  return snap.docs
    .map((d) => ({ id: d.id, ...d.data() }))
    .filter((u: any) => u.uid !== currentUserId && u.onboardingComplete)
}
