import '../models/models.dart';

/// Per-category packaging checklist + maximum delivery time.
/// Source: spec §7.1 (legally required under FDA Philippines).
class FoodSafetyRule {
  const FoodSafetyRule({
    required this.title,
    required this.checklist,
    required this.maxDeliveryMinutes,
  });

  final String title;
  final List<String> checklist;
  final int maxDeliveryMinutes;
}

FoodSafetyRule ruleFor(FoodHandlingCategory category) {
  switch (category) {
    case FoodHandlingCategory.rawFish:
      return const FoodSafetyRule(
        title: 'Raw fish cold chain',
        maxDeliveryMinutes: 45,
        checklist: [
          'Wrap in banana leaf or food-grade plastic',
          'Place in sealed bag',
          'Add ice or ice pack',
          'Photo proof before handover',
          'Foam box mandatory for rider',
        ],
      );
    case FoodHandlingCategory.rawMeat:
      return const FoodSafetyRule(
        title: 'Raw meat handling',
        maxDeliveryMinutes: 30,
        checklist: [
          'Double-bagged (inner food-grade, outer sealed)',
          'Separated from vegetables and cooked food',
          'Ice pack if over 30 minutes',
          'Foam box mandatory',
        ],
      );
    case FoodHandlingCategory.cookedFood:
      return const FoodSafetyRule(
        title: 'Cooked food delivery',
        maxDeliveryMinutes: 20,
        checklist: [
          'Sealed container (not open plates)',
          'Still hot at handover (above 60°C)',
          'Insulated food bag',
          'Upright transport',
        ],
      );
    case FoodHandlingCategory.eggs:
      return const FoodSafetyRule(
        title: 'Egg protection',
        maxDeliveryMinutes: 45,
        checklist: [
          'Original tray or padded box',
          'FRAGILE — EGGS label visible',
          'Separate compartment',
          'No stacking',
        ],
      );
    case FoodHandlingCategory.vegetables:
    case FoodHandlingCategory.dryGoods:
    case FoodHandlingCategory.beverages:
      return const FoodSafetyRule(
        title: 'Standard fresh goods',
        maxDeliveryMinutes: 60,
        checklist: [
          'Separate bags per item type',
          'Keep dry — no exposure to rain',
          'Protect fragile produce',
          'Photo proof if requested',
        ],
      );
  }
}
