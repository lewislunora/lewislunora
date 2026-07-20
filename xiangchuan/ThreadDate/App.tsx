import React, { useState, useEffect } from 'react'
import { StatusBar } from 'expo-status-bar'
import { NavigationContainer } from '@react-navigation/native'
import { onAuthStateChanged } from 'firebase/auth'
import { initFirebase, getFirebaseApp } from './src/config/firebase'
import AppNavigator from './src/navigation/AppNavigator'

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    const { auth } = initFirebase()
    const unsub = onAuthStateChanged(auth, (user) => {
      setIsAuthenticated(!!user)
    })
    return unsub
  }, [])

  if (isAuthenticated === null) return null

  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <AppNavigator isAuthenticated={isAuthenticated} />
    </NavigationContainer>
  )
}
