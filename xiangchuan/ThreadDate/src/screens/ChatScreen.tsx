import React, { useState, useEffect, useRef } from 'react'
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
import { subscribeMessages, sendMessage, Message } from '../services/firestore'
import { getCurrentUser } from '../services/auth'

export default function ChatScreen({ route }: any) {
  const { matchId } = route.params
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const flatRef = useRef<FlatList>(null)
  const user = getCurrentUser()

  useEffect(() => {
    const unsub = subscribeMessages(matchId, (msgs) => {
      setMessages(msgs)
      setLoading(false)
      setTimeout(() => flatRef.current?.scrollToEnd({ animated: true }), 200)
    })
    return unsub
  }, [matchId])

  const handleSend = async () => {
    if (!input.trim() || !user) return
    await sendMessage(matchId, user.uid, input.trim())
    setInput('')
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Colors.primary} />
      </View>
    )
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      <FlatList
        ref={flatRef}
        data={messages}
        keyExtractor={(item) => item.id || Math.random().toString()}
        renderItem={({ item }) => {
          const isMe = item.senderId === user?.uid
          return (
            <View style={[styles.msgRow, isMe && styles.msgRowMe]}>
              <View style={[styles.bubble, isMe ? styles.bubbleMe : styles.bubbleOther]}>
                <Text style={[styles.msgText, isMe && styles.msgTextMe]}>
                  {item.text}
                </Text>
              </View>
            </View>
          )
        }}
        contentContainerStyle={styles.list}
      />
      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          placeholder="輸入訊息..."
          placeholderTextColor={Colors.textMuted}
          value={input}
          onChangeText={setInput}
          multiline
        />
        <TouchableOpacity style={styles.sendBtn} onPress={handleSend}>
          <Text style={styles.sendText}>送出</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, backgroundColor: Colors.background, justifyContent: 'center', alignItems: 'center' },
  list: { padding: Spacing.md, paddingBottom: 20 },
  msgRow: { alignItems: 'flex-start', marginBottom: Spacing.sm },
  msgRowMe: { alignItems: 'flex-end' },
  bubble: {
    maxWidth: '75%',
    borderRadius: 18,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  bubbleOther: { backgroundColor: Colors.surface, borderBottomLeftRadius: 4 },
  bubbleMe: { backgroundColor: Colors.primary, borderBottomRightRadius: 4 },
  msgText: { fontSize: FontSize.md, color: Colors.textSecondary },
  msgTextMe: { color: Colors.text },
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
