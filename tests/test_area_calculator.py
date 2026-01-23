import unittest

from app.domain.area_calculator import CalculatorInput, calculate_house_area


class HouseAreaCalculatorTests(unittest.TestCase):
    def test_single_occupant_minimums(self):
        payload = CalculatorInput(
            occupants=1,
            household_type='single',
            comfort_level='standard',
            future_growth='no',
            extra_rooms=(),
            land_size=None,
            layout='no_preference',
        )
        result = calculate_house_area(payload)
        self.assertEqual(result.summary['bedrooms'], 1)
        self.assertEqual(result.summary['bathrooms'], 1)
        self.assertGreater(result.summary['gross_area'], 0)

    def test_extended_family_adds_bedroom(self):
        payload = CalculatorInput(
            occupants=6,
            household_type='extended_family',
            comfort_level='standard',
            future_growth='maybe',
            extra_rooms=(),
            land_size=None,
            layout='no_preference',
        )
        result = calculate_house_area(payload)
        self.assertGreaterEqual(result.summary['bedrooms'], 5)

    def test_circulation_ratio_bounds(self):
        payload = CalculatorInput(
            occupants=10,
            household_type='family',
            comfort_level='high',
            future_growth='yes',
            extra_rooms=('home_office', 'guest_room', 'storage'),
            land_size=600,
            layout='single_storey',
        )
        result = calculate_house_area(payload)
        ratio = result.summary['circulation_ratio']
        self.assertGreaterEqual(ratio, 0.12)
        self.assertLessEqual(ratio, 0.18)


if __name__ == '__main__':
    unittest.main()
