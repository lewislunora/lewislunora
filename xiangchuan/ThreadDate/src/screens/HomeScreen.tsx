import React, { useState, useEffect } from 'react'
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native'
import { Colors, Spacing, FontSize, APP_NAME } from '../constants/theme'
import { subscribeThreads, Thread } from '../services/firestore'
import ThreadCard from '../components/ThreadCard'

export default function HomeScreen({ navigation }: any) {
  const [threads, setThreads] = useState<Thread[]>([])
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    const unsub = subscribeThreads((data) => {
      setThreads(data)
      setRefreshing(false)
    })
    return unsub
  }, [])

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.logo}>{APP_NAME}</Text>
        <TouchableOpacity
          style={styles.createBtn}
          onPress={() => navigation.navigate('CreateThread')}
        >
          <Text style={styles.createBtnText}>+ 開串</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={threads}
        keyExtractor={(item) => item.id || Math.random().toString()}
        renderItem={({ item }) => <ThreadCard thread={item} onPress={() => navigation.navigate('ThreadDetail', { threadId: item.id })} />}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => setRefreshing(true)}
            tintColor={Colors.primary}
          />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>💬</Text>
            <Text style={styles.emptyText}>還沒有話題串</Text>
            <Text style={styles.emptySub}>按下右上角「+開串」開始第一個對話</Text>
          </View>
        }
      />
    </View>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.md,
  },
  logo: { fontSize: FontSize.xl, fontWeight: '800', color: Colors.primary },
  createBtn: {
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: 20,
  },
  createBtnText: { color: Colors.text, fontWeight: '600' },
  list: { padding: Spacing.md, paddingBottom: 100 },
  empty: { alignItems: 'center', marginTop: 80 },
  emptyIcon: { fontSize: 48, marginBottom: Spacing.md },
  emptyText: { fontSize: FontSize.lg, color: Colors.textSecondary },
  emptySub: { fontSize: FontSize.sm, color: Colors.textMuted, marginTop: Spacing.xs },
})
