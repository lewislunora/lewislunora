import React from 'react'
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Linking,
  ScrollView,
} from 'react-native'
import { Colors, Spacing, FontSize, WEBSITE_URL } from '../constants/theme'
import { getCurrentUser, logout } from '../services/auth'

export default function ProfileScreen({ navigation }: any) {
  const user = getCurrentUser()

  const handleLogout = async () => {
    await logout()
  }

  const handleOpenWebsite = () => {
    Linking.openURL(WEBSITE_URL)
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.profileHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {(user?.displayName || '你')[0]}
          </Text>
        </View>
        <Text style={styles.name}>{user?.displayName || '使用者'}</Text>
        <Text style={styles.email}>{user?.email}</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>設定</Text>

        <TouchableOpacity style={styles.menuItem} onPress={handleOpenWebsite}>
          <Text style={styles.menuIcon}>🌐</Text>
          <Text style={styles.menuText}>造訪官網</Text>
          <Text style={styles.menuArrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.menuItem}>
          <Text style={styles.menuIcon}>🔔</Text>
          <Text style={styles.menuText}>通知設定</Text>
          <Text style={styles.menuArrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.menuItem}>
          <Text style={styles.menuIcon}>🔒</Text>
          <Text style={styles.menuText}>隱私設定</Text>
          <Text style={styles.menuArrow}>›</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>登出</Text>
      </TouchableOpacity>

      <Text style={styles.version}>ThreadDate v1.0.0</Text>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  content: { padding: Spacing.lg },
  profileHeader: { alignItems: 'center', marginTop: Spacing.xl, marginBottom: Spacing.xl },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  avatarText: { fontSize: FontSize.xxl, fontWeight: '700', color: Colors.text },
  name: { fontSize: FontSize.xl, fontWeight: '600', color: Colors.text },
  email: { fontSize: FontSize.sm, color: Colors.textMuted, marginTop: 4 },
  section: { marginBottom: Spacing.lg },
  sectionTitle: { fontSize: FontSize.md, fontWeight: '600', color: Colors.textSecondary, marginBottom: Spacing.sm },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    borderRadius: 12,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  menuIcon: { fontSize: 20, marginRight: Spacing.md },
  menuText: { flex: 1, fontSize: FontSize.md, color: Colors.text },
  menuArrow: { fontSize: FontSize.xl, color: Colors.textMuted },
  logoutBtn: {
    backgroundColor: Colors.error + '20',
    borderRadius: 12,
    padding: Spacing.md,
    alignItems: 'center',
    marginTop: Spacing.md,
  },
  logoutText: { color: Colors.error, fontSize: FontSize.md, fontWeight: '600' },
  version: { textAlign: 'center', color: Colors.textMuted, fontSize: FontSize.xs, marginTop: Spacing.lg },
})
