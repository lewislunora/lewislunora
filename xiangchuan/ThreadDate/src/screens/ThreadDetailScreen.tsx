import React, { useState, useEffect } from 'react'
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native'
import { Colors, Spacing, FontSize } from '../constants/theme'
import { getThread, subscribeComments, addComment, toggleLikeThread, Thread, Comment } from '../services/firestore'
import { getCurrentUser } from '../services/auth'

export default function ThreadDetailScreen({ route, navigation }: any) {
  const { threadId } = route.params
  const [thread, setThread] = useState<Thread | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [newComment, setNewComment] = useState('')
  const [liked, setLiked] = useState(false)

  useEffect(() => {
    getThread(threadId).then(setThread)
    const unsub = subscribeComments(threadId, setComments)
    return unsub
  }, [threadId])

  const handleSendComment = async () => {
    if (!newComment.trim()) return
    const user = getCurrentUser()
    if (!user) return
    await addComment({
      threadId,
      content: newComment.trim(),
      authorId: user.uid,
      authorName: user.displayName || '使用者',
      anonymous: false,
    })
    setNewComment('')
  }

  const handleLike = async () => {
    const user = getCurrentUser()
    if (!user) return
    await toggleLikeThread(threadId, user.uid, liked)
    setLiked(!liked)
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      <FlatList
        data={comments}
        keyExtractor={(item) => item.id || Math.random().toString()}
        ListHeaderComponent={
          thread ? (
            <View style={styles.threadHeader}>
              <View style={styles.tagRow}>
                {thread.tags?.map((tag) => (
                  <View key={tag} style={styles.tag}>
                    <Text style={styles.tagText}>#{tag}</Text>
                  </View>
                ))}
              </View>
              <Text style={styles.threadTitle}>{thread.title}</Text>
              <Text style={styles.threadContent}>{thread.content}</Text>
              <View style={styles.threadMeta}>
                <Text style={styles.author}>
                  {thread.anonymous ? '🕵️ 匿名' : thread.authorName}
                </Text>
                <TouchableOpacity onPress={handleLike} style={styles.likeBtn}>
                  <Text style={styles.likeText}>
                    {liked ? '❤️' : '🤍'} {thread.likes}
                  </Text>
                </TouchableOpacity>
                <Text style={styles.commentCount}>💬 {thread.commentCount}</Text>
              </View>
              <View style={styles.divider} />
              <Text style={styles.replyTitle}>回覆</Text>
            </View>
          ) : (
            <ActivityIndicator color={Colors.primary} style={{ marginTop: 40 }} />
          )
        }
        renderItem={({ item }) => (
          <View style={styles.comment}>
            <Text style={styles.commentAuthor}>
              {item.anonymous ? '🕵️ 匿名' : item.authorName}
            </Text>
            <Text style={styles.commentText}>{item.content}</Text>
          </View>
        )}
        contentContainerStyle={styles.list}
      />

      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          placeholder="寫下你的回覆..."
          placeholderTextColor={Colors.textMuted}
          value={newComment}
          onChangeText={setNewComment}
          multiline
        />
        <TouchableOpacity style={styles.sendBtn} onPress={handleSendComment}>
          <Text style={styles.sendText}>送出</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  list: { padding: Spacing.md },
  threadHeader: { marginBottom: Spacing.md },
  tagRow: { flexDirection: 'row', gap: Spacing.xs, marginBottom: Spacing.sm, flexWrap: 'wrap' },
  tag: { backgroundColor: Colors.primary + '30', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 3 },
  tagText: { color: Colors.primaryLight, fontSize: FontSize.xs },
  threadTitle: { fontSize: FontSize.xl, fontWeight: '700', color: Colors.text },
  threadContent: { fontSize: FontSize.md, color: Colors.textSecondary, marginTop: Spacing.sm, lineHeight: 22 },
  threadMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginTop: Spacing.md,
  },
  author: { color: Colors.textMuted, fontSize: FontSize.sm },
  likeBtn: { padding: 4 },
  likeText: { color: Colors.textMuted, fontSize: FontSize.sm },
  commentCount: { color: Colors.textMuted, fontSize: FontSize.sm },
  divider: { height: 1, backgroundColor: Colors.border, marginVertical: Spacing.md },
  replyTitle: { fontSize: FontSize.md, fontWeight: '600', color: Colors.text, marginBottom: Spacing.sm },
  comment: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  commentAuthor: { fontSize: FontSize.sm, color: Colors.primaryLight, marginBottom: 4 },
  commentText: { fontSize: FontSize.md, color: Colors.textSecondary },
  inputBar: {
    flexDirection: 'row',
    padding: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    backgroundColor: Colors.surface,
    alignItems: 'flex-end',
  },
  input: {
    flex: 1,
    backgroundColor: Colors.background,
    borderRadius: 20,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    color: Colors.text,
    maxHeight: 80,
    marginRight: Spacing.sm,
  },
  sendBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 20,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  sendText: { color: Colors.text, fontWeight: '600' },
})
