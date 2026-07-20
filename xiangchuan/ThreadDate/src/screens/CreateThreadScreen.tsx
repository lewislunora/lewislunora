import React, { useState } from 'react'
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native'
import { Colors, Spacing, FontSize } from '../constants/theme'
import { createThread } from '../services/firestore'
import { getCurrentUser } from '../services/auth'

export default function CreateThreadScreen({ navigation }: any) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState('')
  const [anonymous, setAnonymous] = useState(true)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!title.trim() || !content.trim()) {
      Alert.alert('請填寫標題與內容')
      return
    }
    const user = getCurrentUser()
    if (!user) return

    setLoading(true)
    try {
      const tagList = tags
        .split(/[,，]/)
        .map((t) => t.trim())
        .filter(Boolean)
      await createThread({
        title: title.trim(),
        content: content.trim(),
        tags: tagList,
        authorId: user.uid,
        authorName: anonymous ? '匿名' : (user.displayName || '使用者'),
        authorPhoto: anonymous ? undefined : (user.photoURL || undefined),
        anonymous,
      })
      navigation.goBack()
    } catch (e: any) {
      Alert.alert('發文失敗', e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.cancel}>取消</Text>
        </TouchableOpacity>
        <Text style={styles.title}>開新串</Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={styles.form}>
        <TextInput
          style={styles.input}
          placeholder="標題"
          placeholderTextColor={Colors.textMuted}
          value={title}
          onChangeText={setTitle}
        />
        <TextInput
          style={[styles.input, styles.contentInput]}
          placeholder="寫下你想聊的話題..."
          placeholderTextColor={Colors.textMuted}
          value={content}
          onChangeText={setContent}
          multiline
          textAlignVertical="top"
        />
        <TextInput
          style={styles.input}
          placeholder="標籤（用逗號分隔，如：音樂,台北,美食）"
          placeholderTextColor={Colors.textMuted}
          value={tags}
          onChangeText={setTags}
        />
        <TouchableOpacity
          style={[styles.anonToggle, anonymous && styles.anonToggleActive]}
          onPress={() => setAnonymous(!anonymous)}
        >
          <Text style={[styles.anonText, anonymous && styles.anonTextActive]}>
            {anonymous ? '🕵️ 匿名發文' : '🙂 實名發文'}
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.submitBtn, loading && styles.submitDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color={Colors.text} />
          ) : (
            <Text style={styles.submitText}>發布</Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  cancel: { color: Colors.textSecondary, fontSize: FontSize.md },
  title: { fontSize: FontSize.lg, fontWeight: '600', color: Colors.text },
  form: { padding: Spacing.lg, gap: Spacing.md },
  input: {
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: Spacing.md,
    color: Colors.text,
    fontSize: FontSize.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  contentInput: { height: 150 },
  anonToggle: {
    padding: Spacing.md,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.border,
    alignItems: 'center',
  },
  anonToggleActive: { borderColor: Colors.primary, backgroundColor: Colors.primary + '20' },
  anonText: { color: Colors.textSecondary },
  anonTextActive: { color: Colors.primary, fontWeight: '600' },
  submitBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 12,
    padding: Spacing.md,
    alignItems: 'center',
  },
  submitDisabled: { opacity: 0.6 },
  submitText: { color: Colors.text, fontSize: FontSize.lg, fontWeight: '600' },
})
