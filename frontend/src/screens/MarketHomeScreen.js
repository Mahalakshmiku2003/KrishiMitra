import React from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity, 
  ScrollView,
  Image,
  SafeAreaView,
  Platform
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { theme } from '../theme';

const MarketHomeScreen = ({ navigation }) => {
  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Top AppBar */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <TouchableOpacity activeOpacity={0.8}>
            <MaterialIcons name="menu" size={24} color={theme.colors.primary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Market Intelligence 💰</Text>
        </View>
        <View style={styles.profileContainer}>
          <Image 
            source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDlMOz-oSE5R5DPbFkzAp2g0xP4ZbAvz-oik8YVj4E2UptEYqkNGvNcVHVwiQv66HiqMklVRFcNKTxWt2nYk3ls9a4yP_M1Jy9MNFuP6wcmgr83FBNa88ae8ZiRRl893yKDaMLmMyeSa9Ni9JNdj61jzxICqLjJVhSFkmPCk7AhmJ7itYjAWPI2-_pnsBgCNNgp1ZXGrCPHB_aU5rhAxgf8G3R0M1XGhTFRGTPRQ0E_pmaco9gfQRGYjLlUPDrBLER1sYOUsG1XWdZW' }} 
            style={styles.profileImage} 
          />
        </View>
      </View>

      <ScrollView style={styles.container} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        
        {/* Highlight Banner */}
        <View style={styles.bannerContainer}>
          <View style={styles.bannerIconDeco}>
            <MaterialIcons name="emoji-events" size={100} color="rgba(255,255,255,0.15)" />
          </View>
          <Text style={styles.bannerSubtitle}>KARNATAKA</Text>
          <Text style={styles.bannerTitle}>
            🏆 Best Price Today:{'\n'}Tomato ₹3,369/quintal in Mysore
          </Text>
        </View>

        {/* Navigation Cards Stack */}
        <View style={styles.cardsStack}>
          <TouchableOpacity 
            style={styles.navCard} 
            onPress={() => navigation.navigate('MarketPrices')}
            activeOpacity={0.7}
          >
            <View style={[styles.cardIconBox, { backgroundColor: 'rgba(13, 99, 27, 0.1)' }]}>
              <MaterialIcons name="bar-chart" size={28} color={theme.colors.primary} />
            </View>
            <View style={styles.cardTextContent}>
              <Text style={styles.cardTitle}>Mandi Prices</Text>
              <Text style={styles.cardSubtitle}>Latest prices across India</Text>
            </View>
            <MaterialIcons name="chevron-right" size={24} color={theme.colors.outlineVariant} />
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.navCard} 
            onPress={() => navigation.navigate('NearbyMandis')}
            activeOpacity={0.7}
          >
            <View style={[styles.cardIconBox, { backgroundColor: 'rgba(119, 76, 0, 0.1)' }]}>
              <MaterialIcons name="location-on" size={28} color={theme.colors.tertiary} />
            </View>
            <View style={styles.cardTextContent}>
              <Text style={styles.cardTitle}>Nearby Mandis</Text>
              <Text style={styles.cardSubtitle}>Best price near your location</Text>
            </View>
            <MaterialIcons name="chevron-right" size={24} color={theme.colors.outlineVariant} />
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.navCard} 
            onPress={() => navigation.navigate('PricePrediction')}
            activeOpacity={0.7}
          >
            <View style={[styles.cardIconBox, { backgroundColor: 'rgba(42, 107, 44, 0.1)' }]}>
              <MaterialIcons name="trending-up" size={28} color={theme.colors.secondary} />
            </View>
            <View style={styles.cardTextContent}>
              <Text style={styles.cardTitle}>Price Forecast</Text>
              <Text style={styles.cardSubtitle}>7-day AI prediction trends</Text>
            </View>
            <MaterialIcons name="chevron-right" size={24} color={theme.colors.outlineVariant} />
          </TouchableOpacity>
        </View>

        {/* Trending Crops */}
        <View style={styles.trendingSection}>
          <Text style={styles.sectionHeader}>TRENDING CROPS</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.trendingList}>
            <View style={styles.trendingChip}>
              <Text style={styles.trendingChipText}>Tomato</Text>
              <MaterialIcons name="trending-up" size={18} color={theme.colors.primary} />
            </View>
            <View style={styles.trendingChip}>
              <Text style={styles.trendingChipText}>Onion</Text>
              <MaterialIcons name="trending-down" size={18} color={theme.colors.error} />
            </View>
            <View style={styles.trendingChip}>
              <Text style={styles.trendingChipText}>Wheat</Text>
              <MaterialIcons name="horizontal-rule" size={18} color={theme.colors.outline} />
            </View>
            <View style={styles.trendingChip}>
              <Text style={styles.trendingChipText}>Rice</Text>
              <MaterialIcons name="trending-up" size={18} color={theme.colors.primary} />
            </View>
          </ScrollView>
        </View>

        {/* Footer Info */}
        <View style={styles.footerSection}>
          <View style={styles.dataSourceBox}>
            <MaterialIcons name="info" size={16} color="#9E9E9E" />
            <Text style={styles.dataSourceText}>Prices updated daily from data.gov.in</Text>
          </View>

          {/* Bento Visual */}
          <View style={styles.bentoGrid}>
            <View style={styles.bentoLeft}>
              <Image 
                source={{ uri: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDS8-cSEVzGbBXyYUkTUEf6vv668nqez79qbKxBMDbKz7UPkG8HYXf_iHYrx3w45u2GIKfFv618lRNk9B5pN7Si7iIq3Xsz85mHZrHFElanU03n8fUJWKMWqJHvtX7bJD0KqR7oWynRXYAHVlOfNrwEBxWq_pGaRC0oURY7dfA5UF-w4RQ89BrmLW2PT54ePUT4rLTSkEcqDpf36XHBYIiOZ2-wPIaI75c1Sobi7Vp3XTk_7ECgNjz0moDNzNz7AaG_cdWY5VQDsRlk' }} 
                style={styles.bentoImageBg} 
              />
              <View style={styles.bentoOverlay} />
              <View style={styles.bentoContent}>
                <Text style={styles.bentoBigNumber}>92%</Text>
                <Text style={styles.bentoLabel}>PRICE ACCURACY</Text>
              </View>
            </View>
            
            <View style={styles.bentoRight}>
              <View style={styles.advisoryGradient} />
              <View style={styles.bentoRightContent}>
                <MaterialIcons name="psychology" size={32} color={theme.colors.onPrimaryContainer} />
                <Text style={styles.advisoryText}>AI Advisory active for Mysore district</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Bottom padding for tab bar */}
        <View style={{height: 100}} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.surfaceContainerLow,
    paddingTop: Platform.OS === 'android' ? 40 : 0,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingVertical: 16,
    backgroundColor: theme.colors.surfaceContainerLow,
    zIndex: 10,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: theme.colors.primary,
    letterSpacing: -0.5,
  },
  profileContainer: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: 'rgba(46, 125, 50, 0.2)',
    overflow: 'hidden',
  },
  profileImage: {
    width: '100%',
    height: '100%',
  },
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 8,
    gap: 32,
  },
  bannerContainer: {
    backgroundColor: theme.colors.tertiary,
    borderRadius: 16,
    padding: 24,
    overflow: 'hidden',
    position: 'relative',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
  },
  bannerIconDeco: {
    position: 'absolute',
    top: -20,
    right: -20,
    transform: [{ rotate: '12deg' }],
  },
  bannerSubtitle: {
    color: 'rgba(255,255,255,0.8)',
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 2,
    marginBottom: 4,
    ...theme.typography.label,
  },
  bannerTitle: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 26,
  },
  cardsStack: {
    gap: 16,
  },
  navCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  cardIconBox: {
    width: 48,
    height: 48,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 16,
  },
  cardTextContent: {
    flex: 1,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: theme.colors.onSurface,
  },
  cardSubtitle: {
    fontSize: 14,
    color: theme.colors.onSurfaceVariant,
    marginTop: 2,
  },
  trendingSection: {
    marginTop: 8,
  },
  sectionHeader: {
    fontSize: 14,
    fontWeight: '700',
    color: theme.colors.onSurfaceVariant,
    letterSpacing: 1,
    marginBottom: 16,
  },
  trendingList: {
    paddingRight: 24,
    gap: 12,
  },
  trendingChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: theme.colors.surfaceContainerLowest,
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: 'rgba(191, 202, 186, 0.2)',
  },
  trendingChipText: {
    fontSize: 14,
    fontWeight: '600',
    color: theme.colors.onSurface,
  },
  footerSection: {
    gap: 24,
    alignItems: 'center',
  },
  dataSourceBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dataSourceText: {
    fontSize: 12,
    fontWeight: '500',
    color: '#9E9E9E',
  },
  bentoGrid: {
    flexDirection: 'row',
    width: '100%',
    gap: 16,
  },
  bentoLeft: {
    flex: 1,
    aspectRatio: 1,
    backgroundColor: theme.colors.surfaceContainerHighest,
    borderRadius: 24,
    overflow: 'hidden',
  },
  bentoImageBg: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    opacity: 0.6,
  },
  bentoOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  bentoContent: {
    flex: 1,
    padding: 16,
    justifyContent: 'flex-start',
  },
  bentoBigNumber: {
    fontSize: 32,
    fontWeight: '900',
    color: theme.colors.onPrimaryFixed,
  },
  bentoLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.onPrimaryFixedVariant,
    letterSpacing: 1,
  },
  bentoRight: {
    flex: 1,
    aspectRatio: 1,
    backgroundColor: theme.colors.primaryContainer,
    borderRadius: 24,
    overflow: 'hidden',
  },
  advisoryGradient: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    backgroundColor: theme.colors.primary,
    opacity: 0.4,
  },
  bentoRightContent: {
    flex: 1,
    padding: 16,
    justifyContent: 'space-between',
    zIndex: 1,
  },
  advisoryText: {
    fontSize: 14,
    fontWeight: '700',
    color: theme.colors.onPrimaryContainer,
    lineHeight: 20,
  },
});

export default MarketHomeScreen;
