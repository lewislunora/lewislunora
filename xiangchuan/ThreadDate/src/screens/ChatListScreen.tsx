import React, { useState, useEffect } from 'react'
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native'
import { Colors, Spacing, FontSize } from '../constants/theme'
import { subscribeMatches } from '../services/firestore'
import { getCurrentUser } from '../services/auth'

export default function ChatListScreen({ navigation }: any) {
  const [matches, setMatches] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const user = getCurrentUser()

  useEffect(() => {
    if (!user) return
    const unsub = subscribeMatches(user.uid, (data) => {
      setMatches(data)
      setLoading(false)
    })
    return unsub
  }, [])

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>配對聊天</Text>
      <FlatList
        data={matches}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => {
          const otherUserId = item.users?.find((id: string) => id !== user?.uid)
          return (
            <TouchableOpacity
              style={styles.matchCard}
              onPress={() => navigation.navigate('Chat', { matchId: item.id, otherUserId })}
            >
              <View style={styles.avatar}>
                <Text style={styles.avatarText}>💬</Text>
              </View>
              <View style={styles.info}>
                <Text style={styles.lastMsg}>
                  {item.lastMessage || '開始聊天吧！'}
                </Text>
                <Text style={styles.time}>
                  {item.lastMessageAt?.toDate?.()?.toLocaleString() || ''}
                </Text>
              </View>
            </TouchableOpacity>
          )
        }}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>💕</Text>
            <Text style={styles.emptyText}>還沒有配對</Text>
            <Text style={styles.emptySub}>去「發現」頁面找新朋友吧！</Text>
          </View>
        }
        contentContainerStyle={styles.list}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, justifyContent: 'center', alignItems: 'center' },
  title: {
    fontSize: FontSize.xl,
    fontWeight: '700',
    color: Colors.text,
    padding: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  list: { padding: Spacing.md },
  matchCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: Colors.primaryDark,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.md,
  },
  avatarText: { fontSize: 24 },
  info: { flex: 1 },
  lastMsg: { fontSize: FontSize.md, color: Colors.text, fontWeight: '500' },
  time: { fontSize: FontSize.xs, color: Colors.textMuted, marginTop: 4 },
  empty: { alignItems: 'center', marginTop: 60 },
  emptyIcon: { fontSize: 48, marginBottom: Spacing.md },
  emptyText: { color: Colors.textSecondary, fontSize: FontSize.lg },
  emptySub: { color: Colors.textMuted, fontSize: FontSize.sm, marginTop: Spacing.xs },
})
