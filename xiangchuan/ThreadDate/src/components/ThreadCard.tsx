import React from 'react'
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { Colors, Spacing, FontSize } from '../constants/theme'
import { Thread } from '../services/firestore'

export default function ThreadCard({ thread, onPress }: { thread: Thread; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.tagRow}>
        {thread.tags?.slice(0, 3).map((tag) => (
          <View key={tag} style={styles.tag}>
            <Text style={styles.tagText}>#{tag}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.title} numberOfLines={2}>
        {thread.title}
      </Text>
      <Text style={styles.content} numberOfLines={3}>
        {thread.content}
      </Text>
      <View style={styles.footer}>
        <Text style={styles.author}>
          {thread.anonymous ? '🕵️ 匿名' : thread.authorName}
        </Text>
        <View style={styles.stats}>
          <Text style={styles.stat}>❤️ {thread.likes || 0}</Text>
          <Text style={styles.stat}>💬 {thread.commentCount || 0}</Text>
        </View>
      </View>
    </TouchableOpacity>
  )
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  tagRow: { flexDirection: 'row', gap: Spacing.xs, marginBottom: Spacing.sm, flexWrap: 'wrap' },
  tag: { backgroundColor: Colors.primary + '25', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  tagText: { color: Colors.primaryLight, fontSize: 11 },
  title: { fontSize: FontSize.lg, fontWeight: '700', color: Colors.text, marginBottom: 4 },
  content: { fontSize: FontSize.sm, color: Colors.textSecondary, lineHeight: 20 },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.md,
  },
  author: { color: Colors.textMuted, fontSize: FontSize.xs },
  stats: { flexDirection: 'row', gap: Spacing.md },
  stat: { color: Colors.textMuted, fontSize: FontSize.xs },
})
