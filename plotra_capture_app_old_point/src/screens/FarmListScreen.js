import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Image,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { farmAPI } from '../services/api';

const FarmListScreen = ({ navigation }) => {
  const { user, logout } = useAuth();
  const [farms, setFarms] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadFarms();
  }, []);

  const loadFarms = async () => {
    try {
      setIsLoading(true);
      const response = await farmAPI.getMyFarms();
      setFarms(response.data || []);
    } catch (error) {
      console.error('Error loading farms:', error);
      Alert.alert('Error', 'Failed to load farms. Please try again.');
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      // Navigation handled by stack navigator
    } catch (error) {
      Alert.alert('Error', 'Failed to logout');
    }
  };

  const renderFarmCard = ({ item }) => {
    const farmName = item.farm_name || `Farm #${item.id}`;
    const area = item.total_area_hectares?.toFixed(2) || '0.00';

    return (
      <TouchableOpacity
        style={styles.card}
        onPress={() => navigation.navigate('FarmDetail', { farm: item })}
      >
        <View style={styles.cardContent}>
          <View style={styles.cardHeader}>
            <Text style={styles.farmName} numberOfLines={1}>
              {farmName}
            </Text>
            <View style={[
              styles.statusBadge,
              item.compliance_status?.toLowerCase().includes('compliant') && styles.statusCompliant,
              item.compliance_status?.toLowerCase().includes('non-compliant') && styles.statusNonCompliant,
              item.compliance_status?.toLowerCase().includes('high risk') && styles.statusHighRisk,
            ]}>
              <Text style={styles.statusText}>
                {item.compliance_status || 'No Status'}
              </Text>
            </View>
          </View>

          <View style={styles.details}>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Area:</Text>
              <Text style={styles.detailValue}>{area} hectares</Text>
            </View>
            {item.coffee_varieties && item.coffee_varieties.length > 0 && (
              <View style={styles.detailRow}>
                <Text style={styles.detailLabel}>Varieties:</Text>
                <Text style={styles.detailValue}>
                  {item.coffee_varieties.slice(0, 3).join(', ')}
                  {item.coffee_varieties.length > 3 && ` (+${item.coffee_varieties.length - 3} more)`}
                </Text>
              </View>
            )}
          </View>

          {item.parcels && item.parcels.length > 0 && (
            <View style={styles.parcelInfo}>
              <Text style={styles.parcelText}>
                {item.parcels.length} parcel{item.parcels.length !== 1 ? 's' : ''} registered
              </Text>
            </View>
          )}

          <View style={styles.riskIndicator}>
            <Text style={styles.riskLabel}>EUDR Risk Score:</Text>
            <View style={styles.riskBarContainer}>
              <View
                style={[
                  styles.riskBar,
                  {
                    width: `${Math.min((item.deforestation_risk_score || 0), 100)}%`,
                    backgroundColor:
                      (item.deforestation_risk_score || 0) < 30 ? '#4caf50' :
                      (item.deforestation_risk_score || 0) < 70 ? '#ff9800' : '#f44336'
                  },
                ]}
              />
            </View>
            <Text style={styles.riskScore}>
              {item.deforestation_risk_score?.toFixed(1) || '0.0'}%
            </Text>
          </View>
        </View>

        <TouchableOpacity
          style={styles.captureButton}
          onPress={() => navigation.navigate('Capture', { farm: item })}
        >
          <Text style={styles.captureButtonText}>Capture GPS</Text>
        </TouchableOpacity>
      </TouchableOpacity>
    );
  };

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#6f4e37" />
        <Text style={styles.loadingText}>Loading your farms...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.welcomeText}>Welcome,</Text>
          <Text style={styles.userName}>
            {user?.first_name} {user?.last_name}
          </Text>
          {user?.phone && (
            <Text style={styles.userPhone}>{user.phone}</Text>
          )}
        </View>
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
      </View>

      {farms.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Image
            source={{ uri: 'https://cdn-icons-png.flaticon.com/512/3144/3144456.png' }}
            style={styles.emptyIcon}
            resizeMode="contain"
          />
          <Text style={styles.emptyTitle}>No Farms Registered</Text>
          <Text style={styles.emptyText}>
            You haven't registered any farms yet.{'\n'}
            Please contact your administrator or register via the web portal.
          </Text>
        </View>
      ) : (
        <FlatList
          data={farms}
          renderItem={renderFarmCard}
          keyExtractor={(item) => `farm-${item.id}`}
          contentContainerStyle={styles.list}
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            loadFarms();
          }}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: 20,
    paddingTop: 60,
    backgroundColor: '#6f4e37',
  },
  welcomeText: {
    color: '#fff',
    fontSize: 14,
    opacity: 0.9,
  },
  userName: {
    color: '#fff',
    fontSize: 22,
    fontWeight: 'bold',
  },
  userPhone: {
    color: '#fff',
    fontSize: 12,
    opacity: 0.8,
    marginTop: 2,
  },
  logoutButton: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
  },
  logoutText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: 14,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: '#666',
  },
  list: {
    padding: 16,
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    overflow: 'hidden',
  },
  cardContent: {
    padding: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  farmName: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    flex: 1,
    marginRight: 8,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  statusCompliant: {
    backgroundColor: '#e8f5e9',
  },
  statusNonCompliant: {
    backgroundColor: '#ffebee',
  },
  statusHighRisk: {
    backgroundColor: '#fff3e0',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#333',
  },
  details: {
    marginBottom: 12,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  detailLabel: {
    fontSize: 14,
    color: '#666',
  },
  detailValue: {
    fontSize: 14,
    color: '#333',
    fontWeight: '500',
  },
  parcelInfo: {
    marginBottom: 12,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: '#eee',
  },
  parcelText: {
    fontSize: 13,
    color: '#6f4e37',
    fontWeight: '500',
  },
  riskIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  riskLabel: {
    fontSize: 13,
    color: '#666',
    marginRight: 8,
  },
  riskBarContainer: {
    flex: 1,
    height: 8,
    backgroundColor: '#e0e0e0',
    borderRadius: 4,
    overflow: 'hidden',
  },
  riskBar: {
    height: '100%',
    borderRadius: 4,
  },
  riskScore: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#333',
    marginLeft: 8,
  },
  captureButton: {
    backgroundColor: '#6f4e37',
    paddingVertical: 14,
    alignItems: 'center',
  },
  captureButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyIcon: {
    width: 120,
    height: 120,
    marginBottom: 20,
    opacity: 0.6,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    lineHeight: 24,
  },
});

export default FarmListScreen;
