import React from 'react'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { NavigationContainer } from '@react-navigation/native'
import { Text, View } from 'react-native'
import { Colors, FontSize, WEBSITE_URL } from '../constants/theme'

import HomeScreen from '../screens/HomeScreen'
import CreateThreadScreen from '../screens/CreateThreadScreen'
import ThreadDetailScreen from '../screens/ThreadDetailScreen'
import MatchScreen from '../screens/MatchScreen'
import ChatListScreen from '../screens/ChatListScreen'
import ChatScreen from '../screens/ChatScreen'
import ProfileScreen from '../screens/ProfileScreen'
import LoginScreen from '../screens/LoginScreen'
import RegisterScreen from '../screens/RegisterScreen'

const Stack = createNativeStackNavigator()
const Tab = createBottomTabNavigator()

function TabIcon({ label, focused }: { label: string; focused: boolean }) {
  const icons: Record<string, string> = {
    '廣場': '💬',
    '發現': '❤️',
    '配對': '💕',
    '個人': '👤',
  }
  return (
    <View style={{ alignItems: 'center' }}>
      <Text style={{ fontSize: 20 }}>{icons[label] || '●'}</Text>
    </View>
  )
}

function HomeTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused }) => <TabIcon label={route.name} focused={focused} />,
        tabBarActiveTintColor: Colors.primary,
        tabBarInactiveTintColor: Colors.textMuted,
        tabBarStyle: {
          backgroundColor: Colors.surface,
          borderTopColor: Colors.border,
          height: 60,
          paddingBottom: 8,
          paddingTop: 4,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '500' },
        headerShown: false,
      })}
    >
      <Tab.Screen name="廣場" component={HomeScreen} />
      <Tab.Screen name="發現" component={MatchScreen} />
      <Tab.Screen name="配對" component={ChatListScreen} />
      <Tab.Screen name="個人" component={ProfileScreen} />
    </Tab.Navigator>
  )
}

export default function AppNavigator({ isAuthenticated }: { isAuthenticated: boolean }) {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: Colors.surface },
        headerTintColor: Colors.text,
        headerTitleStyle: { fontWeight: '600' },
        contentStyle: { backgroundColor: Colors.background },
      }}
    >
      {isAuthenticated ? (
        <>
          <Stack.Screen name="Main" component={HomeTabs} options={{ headerShown: false }} />
          <Stack.Screen name="CreateThread" component={CreateThreadScreen} options={{ headerShown: false }} />
          <Stack.Screen name="ThreadDetail" component={ThreadDetailScreen} options={{ title: '話題串' }} />
          <Stack.Screen name="Chat" component={ChatScreen} options={{ title: '聊天' }} />
        </>
      ) : (
        <>
          <Stack.Screen name="Login" component={LoginScreen} options={{ headerShown: false }} />
          <Stack.Screen name="Register" component={RegisterScreen} options={{ headerShown: false }} />
        </>
      )}
    </Stack.Navigator>
  )
}
