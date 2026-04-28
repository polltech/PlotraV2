import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';

const SubmittedScreen = () => {
  const route = useRoute();
  const navigation = useNavigation();
  const { captureId, farmId, area, points, status } = route.params;

  return (
    <View style={styles.container}>
      <View style={styles.iconContainer}>
        <Text style={styles.icon}>✓</Text>
        <Text style={styles.statusText}>Submitted</Text>
        <Text style={styles.subText}>
          Polygon received by Plotra{'\n'}
          {farmId} is ready for satellite review
        </Text>
      </View>

      <View style={styles.summaryCard}>
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Farm ID</Text>
          <Text style={styles.summaryValue}>{farmId}</Text>
        </View>
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Area</Text>
          <Text style={styles.summaryValue}>{area?.toFixed(2) || '0.00'} ha</Text>
        </View>
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Points</Text>
          <Text style={styles.summaryValue}>{points} pts</Text>
        </View>
      </View>

      <View style={styles.statusBadge}>
        <Text style={styles.statusBadgeText}>Synced</Text>
      </View>

      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => navigation.navigate('FarmIDEntry')}
        >
          <Text style={styles.primaryButtonText}>Capture another farm →</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => navigation.navigate('QueueList')}
        >
          <Text style={styles.secondaryButtonText}>View all records</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 20,
    justifyContent: 'center',
  },
  iconContainer: {
    alignItems: 'center',
    marginBottom: 40,
  },
  icon: {
    fontSize: 80,
    color: '#4caf50',
    marginBottom: 16,
  },
  statusText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#4caf50',
    marginBottom: 8,
  },
  subText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    lineHeight: 20,
  },
  summaryCard: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    marginBottom: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  summaryLabel: {
    fontSize: 14,
    color: '#666',
  },
  summaryValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  statusBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#e8f5e9',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    marginBottom: 30,
  },
  statusBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#2e7d32',
  },
  actions: {
    gap: 12,
  },
  primaryButton: {
    backgroundColor: '#6f4e37',
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButton: {
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#6f4e37',
  },
  secondaryButtonText: {
    color: '#6f4e37',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default SubmittedScreen;
