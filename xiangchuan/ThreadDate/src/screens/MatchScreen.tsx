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
import { getDiscoverUsers, likeUser, checkMutualLike, createMatch } from '../services/firestore'
import { getCurrentUser } from '../services/auth'

export default function MatchScreen({ navigation }: any) {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    const user = getCurrentUser()
    if (!user) return
    const data = await getDiscoverUsers(user.uid)
    setUsers(data)
    setLoading(false)
  }

  const handleLike = async (targetUser: any) => {
    const user = getCurrentUser()
    if (!user) return
    await likeUser(user.uid, targetUser.uid)
    const isMatch = await checkMutualLike(user.uid, targetUser.uid)
    if (isMatch) {
      await createMatch(user.uid, targetUser.uid)
      alert('🎉 配對成功！你們互相喜歡！')
      loadUsers()
    } else {
      alert('已送出喜歡 ❤️')
      setUsers((prev) => prev.filter((u) => u.uid !== targetUser.uid))
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>發現新朋友</Text>
      <FlatList
        data={users}
        keyExtractor={(item) => item.uid}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>
                {(item.displayName || '?')[0]}
              </Text>
            </View>
            <View style={styles.info}>
              <Text style={styles.name}>{item.displayName}</Text>
              <Text style={styles.age}>{item.birthDate || '年齡不詳'}</Text>
              {item.bio ? <Text style={styles.bio}>{item.bio}</Text> : null}
            </View>
            <TouchableOpacity
              style={styles.likeBtn}
              onPress={() => handleLike(item)}
            >
              <Text style={styles.likeBtnText}>❤️</Text>
            </TouchableOpacity>
          </View>
        )}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>目前沒有更多使用者</Text>
          </View>
        }
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
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.md,
  },
  avatarText: { fontSize: FontSize.xl, fontWeight: '700', color: Colors.text },
  info: { flex: 1 },
  name: { fontSize: FontSize.md, fontWeight: '600', color: Colors.text },
  age: { fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 2 },
  bio: { fontSize: FontSize.sm, color: Colors.textSecondary, marginTop: 4 },
  likeBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: Colors.accent + '30',
    justifyContent: 'center',
    alignItems: 'center',
  },
  likeBtnText: { fontSize: 24 },
  empty: { alignItems: 'center', marginTop: 60 },
  emptyText: { color: Colors.textMuted, fontSize: FontSize.md },
})
